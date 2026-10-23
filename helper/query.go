package main

import (
	"fmt"
	"go/types"
	"io"
	"sort"
	"strings"

	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/cha"
	"golang.org/x/tools/go/callgraph/vta"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

// qAnalysis is the program the CP5b query modes (lift, callers, callees) work on: the same
// CHA-seeded VTA call graph as reach, but
//   - it can be built for a library (no main packages): every function is a node and a root;
//   - a closure is folded into its outermost enclosing declared function, so "who calls f" and
//     "which exported function contains the call" are answered for declared functions, which are
//     the only things a vulndb symbol can name;
//   - modulePkgs records which packages were matched by the request (the module under study).
type qAnalysis struct {
	prog       *ssa.Program
	g          *graph
	in         [][]gEdge             // reverse adjacency
	byObj      map[*types.Func][]int // declared function -> nodes
	entry      map[int]bool          // exported entry points
	inModule   []bool                // node belongs to a package the request matched
	modulePkgs map[string]bool
	objOf      map[int]*types.Func // node -> the declaration it implements
	skipped    map[string]string   // package path -> first error, for packages left out at load time
	load       *LoadInfo
	npkgs      int
}

// loadQuery loads the program for a query mode. With main_packages it behaves like reach (strict
// loading, roots are main and init). Without, it loads the `packages` patterns (default ./...)
// and tolerates broken packages: a package with its own errors, or importing one that has, is left
// out and counted in LoadInfo, because one broken example directory must not hide the library.
func loadQuery(req *Request, stderr io.Writer) (*qAnalysis, *Error) {
	appMode := len(req.MainPackages) > 0
	var pkgs []*packages.Package
	var dir string
	var skipped map[string]string
	info := &LoadInfo{Mode: "LIBRARY", FirstErrors: []string{}}
	if appMode {
		info.Mode = "APP"
		var err *Error
		pkgs, dir, err = loadPackages(req, packages.LoadAllSyntax|packages.NeedModule)
		if err != nil {
			return nil, err
		}
		info.PackagesMatched = len(pkgs)
	} else {
		var err *Error
		pkgs, dir, skipped, err = loadLibrary(req, info)
		if err != nil {
			return nil, err
		}
	}
	prog, ssaPkgs := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()
	modulePkgs := map[string]bool{}
	for _, p := range pkgs {
		modulePkgs[p.PkgPath] = true
	}
	if appMode {
		// The module under study is the main packages' own module, not only the main packages.
		mainModules := map[string]bool{}
		for _, p := range pkgs {
			if p.Module != nil {
				mainModules[p.Module.Path] = true
			}
		}
		packages.Visit(pkgs, nil, func(p *packages.Package) {
			if p.Module != nil && mainModules[p.Module.Path] {
				modulePkgs[p.PkgPath] = true
			}
		})
	}
	var set map[*ssa.Function]bool
	var cg *callgraph.Graph
	var rootFns []*ssa.Function
	if appMode {
		for i, sp := range ssaPkgs {
			if sp == nil {
				return nil, errf(CodeLoadFailed, "no SSA package for "+pkgs[i].PkgPath)
			}
			mainFn := sp.Func("main")
			if mainFn == nil {
				return nil, errf(CodeLoadFailed, "package "+pkgs[i].PkgPath+" has no main function")
			}
			if initFn := sp.Func("init"); initFn != nil {
				rootFns = append(rootFns, initFn)
			}
			rootFns = append(rootFns, mainFn)
		}
		cg = vtaCallGraph(prog, rootFns)
		set = forwardSlice(rootFns, cg)
	} else {
		all := ssautil.AllFunctions(prog)
		cg = vta.CallGraph(all, cha.CallGraph(prog))
		set = all
	}
	a := buildQuery(prog, cg, set, modulePkgs, newRelativizer(dir))
	a.load = info
	a.skipped = skipped
	a.npkgs = countPackages(pkgs)
	fmt.Fprintf(stderr, "vt-helper: %s mode, %d packages (%d matched, %d skipped), %d nodes, %d edges\n",
		info.Mode, a.npkgs, info.PackagesMatched, info.PackagesSkipped, len(a.g.nodes), a.g.edgeCount())
	return a, nil
}

// loadLibrary loads the request's package patterns and drops packages that did not load cleanly.
func loadLibrary(req *Request, info *LoadInfo) ([]*packages.Package, string, map[string]string, *Error) {
	dir, e := moduleDirAbs(req)
	if e != nil {
		return nil, "", nil, e
	}
	cfg := &packages.Config{Mode: packages.LoadAllSyntax, Dir: dir, Env: buildEnv(req), Tests: false}
	if len(req.Build.Tags) > 0 {
		cfg.BuildFlags = []string{"-tags=" + strings.Join(req.Build.Tags, ",")}
	}
	patterns := req.Packages
	if len(patterns) == 0 {
		patterns = []string{"./..."}
	}
	pkgs, err := packages.Load(cfg, patterns...)
	if err != nil {
		return nil, "", nil, errf(CodeLoadFailed, firstLine(err.Error()))
	}
	if len(pkgs) == 0 {
		return nil, "", nil, errf(CodeLoadFailed, "no packages matched "+strings.Join(patterns, " "))
	}
	info.PackagesMatched = len(pkgs)
	bad := map[*packages.Package]string{}
	var firstBad func(p *packages.Package) string
	firstBad = func(p *packages.Package) string {
		if msg, ok := bad[p]; ok {
			return msg
		}
		bad[p] = "" // cycle guard: a package in a cycle is judged by its own errors and the rest
		msg := ""
		if len(p.Errors) > 0 {
			msgs := make([]string, 0, len(p.Errors))
			for _, pe := range p.Errors {
				msgs = append(msgs, firstLine(pe.Error()))
			}
			sort.Strings(msgs)
			msg = msgs[0]
		} else {
			paths := make([]string, 0, len(p.Imports))
			for path := range p.Imports {
				paths = append(paths, path)
			}
			sort.Strings(paths)
			for _, path := range paths {
				if m := firstBad(p.Imports[path]); m != "" {
					msg = m
					break
				}
			}
		}
		bad[p] = msg
		return msg
	}
	var good []*packages.Package
	skipped := map[string]string{}
	var errs []string
	for _, p := range pkgs {
		if msg := firstBad(p); msg != "" {
			info.PackagesSkipped++
			skipped[p.PkgPath] = msg
			errs = append(errs, p.PkgPath+": "+msg)
			continue
		}
		good = append(good, p)
	}
	sort.Strings(errs)
	if len(errs) > 5 {
		errs = errs[:5]
	}
	info.FirstErrors = append(info.FirstErrors, errs...)
	if len(good) == 0 {
		return nil, "", nil, errf(CodeLoadFailed, strings.Join(info.FirstErrors, "; "))
	}
	return good, dir, skipped, nil
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	return s
}

// outermost is the declared (or package-level) function a closure is lexically part of.
func outermost(fn *ssa.Function) *ssa.Function {
	for fn.Parent() != nil {
		fn = fn.Parent()
	}
	return fn
}

// buildQuery reduces an SSA call graph to a graph over outermost functions.
func buildQuery(prog *ssa.Program, cg *callgraph.Graph, set map[*ssa.Function]bool, modulePkgs map[string]bool, rel relativizer) *qAnalysis {
	b := newGraphBuilder()
	keys := map[*ssa.Function]string{}
	used := map[string]bool{}
	keyOf := func(fn *ssa.Function) string {
		if k, ok := keys[fn]; ok {
			return k
		}
		base := fn.String() + "\x00" + fn.Synthetic + "\x00" + prog.Fset.Position(fn.Pos()).String()
		k := base
		for i := 2; used[k]; i++ {
			k = fmt.Sprintf("%s#%d", base, i)
		}
		keys[fn], used[k] = k, true
		return k
	}
	add := func(fn *ssa.Function) int {
		return b.node(keyOf(fn), node{Pkg: funcPkgPath(fn), Sym: funcSymbol(fn)})
	}
	// Owners are the nodes; visit them in a fixed order so keys (and tie-breaks) are deterministic.
	ownerSet := map[*ssa.Function]bool{}
	for fn := range set {
		ownerSet[outermost(fn)] = true
	}
	owners := make([]*ssa.Function, 0, len(ownerSet))
	for fn := range ownerSet {
		owners = append(owners, fn)
	}
	sort.Slice(owners, func(i, j int) bool { return keyOf(owners[i]) < keyOf(owners[j]) })
	for _, fn := range owners {
		add(fn)
	}
	fns := make([]*ssa.Function, 0, len(set))
	for fn := range set {
		fns = append(fns, fn)
	}
	sort.Slice(fns, func(i, j int) bool { return keyOf(fns[i]) < keyOf(fns[j]) })
	for _, fn := range fns {
		n := cg.Nodes[fn]
		if n == nil {
			continue
		}
		from := outermost(fn)
		for _, e := range n.Out {
			callee := e.Callee.Func
			to := outermost(callee)
			if from == to && callee.Parent() != nil {
				continue // a function and its own closures are one node
			}
			if !set[callee] && !ownerSet[to] {
				continue
			}
			site, kind := Site{}, KindStatic
			if e.Site != nil {
				pos := prog.Fset.Position(e.Site.Pos())
				site = Site{File: rel.file(pos.Filename), Line: pos.Line}
				if e.Site.Common().StaticCallee() == nil {
					kind = KindDynamic
				}
			}
			b.edge(add(from), add(to), site, kind)
		}
	}
	g, ids := b.freeze()
	a := &qAnalysis{prog: prog, g: g, byObj: map[*types.Func][]int{}, entry: map[int]bool{},
		inModule: make([]bool, len(g.nodes)), modulePkgs: modulePkgs, objOf: map[int]*types.Func{}}
	a.in = make([][]gEdge, len(g.nodes))
	for _, es := range g.out {
		for _, e := range es {
			a.in[e.To] = append(a.in[e.To], e)
		}
	}
	for _, fn := range owners {
		id := ids[keyOf(fn)]
		a.inModule[id] = modulePkgs[funcPkgPath(fn)]
		if obj := declObject(fn); obj != nil {
			a.byObj[obj] = append(a.byObj[obj], id)
			a.objOf[id] = obj
			if isEntryPoint(obj) {
				a.entry[id] = true
			}
		}
	}
	for _, v := range a.byObj {
		sort.Ints(v)
	}
	return a
}

// hasInternalElement reports whether an import path has an "internal" element.
func hasInternalElement(path string) bool {
	for _, p := range strings.Split(path, "/") {
		if p == "internal" {
			return true
		}
	}
	return false
}

// isEntryPoint is the lifting definition of an exported entry point: an exported function, or
// an exported method of an exported type, in a package that is neither internal nor main.
func isEntryPoint(obj *types.Func) bool {
	pkg := obj.Pkg()
	if pkg == nil || pkg.Name() == "main" || hasInternalElement(pkg.Path()) || !obj.Exported() {
		return false
	}
	sig, ok := obj.Type().(*types.Signature)
	if !ok {
		return false
	}
	recv := sig.Recv()
	if recv == nil {
		return true
	}
	n := namedOf(recv.Type())
	return n != nil && n.Obj().Exported()
}

// isGenericDecl reports a function or method that is generic itself or has a generic receiver.
func isGenericDecl(obj *types.Func) bool {
	sig, ok := obj.Type().(*types.Signature)
	if !ok {
		return false
	}
	if sig.TypeParams().Len() > 0 || sig.RecvTypeParams().Len() > 0 {
		return true
	}
	if recv := sig.Recv(); recv != nil {
		if n := namedOf(recv.Type()); n != nil && n.TypeParams().Len() > 0 {
			return true
		}
	}
	return false
}

// resolveSeed finds the nodes of a target, or the reason it has none.
func (a *qAnalysis) resolveSeed(t Target) (obj *types.Func, ids []int, notInProgram bool, err *Error) {
	obj, notInProgram, err = lookupTarget(a.prog, t)
	if err != nil {
		return nil, nil, false, err
	}
	if notInProgram {
		if msg, ok := a.skipped[t.Package]; ok {
			return nil, nil, false, errf(CodePackageUnloaded, "package "+t.Package+" was left out of the program: "+msg)
		}
		return nil, nil, true, nil
	}
	return obj, a.byObj[obj], false, nil
}

func nodeTarget(g *graph, id int) Target {
	return Target{Package: g.nodes[id].Pkg, Symbol: g.nodes[id].Sym}
}

// entryTarget names an entry point by its declaration (no instance suffix, no closure suffix).
func (a *qAnalysis) entryTarget(id int) Target {
	if obj, ok := a.objOf[id]; ok {
		return Target{Package: obj.Pkg().Path(), Symbol: objSymbol(obj)}
	}
	return nodeTarget(a.g, id)
}

// objSymbol is the vulndb-form symbol of a declared function or method.
func objSymbol(obj *types.Func) string {
	if sig, ok := obj.Type().(*types.Signature); ok && sig.Recv() != nil {
		if n := namedOf(sig.Recv().Type()); n != nil {
			return n.Obj().Name() + "." + obj.Name()
		}
	}
	return obj.Name()
}

// withLoad lets a query mode hand its load report to the response writer.
type withLoad struct {
	results any
	load    *LoadInfo
}

func runLift(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	a, err := loadQuery(req, stderr)
	if err != nil {
		return nil, nil, err
	}
	rules := req.LiftRules
	if len(rules) == 0 {
		rules = []string{RuleNearest, RuleAll}
	}
	depthLimit := req.Limits.MaxLiftDepth
	if depthLimit == 0 {
		depthLimit = defaultMaxLiftDepth
	}
	results := make([]LiftResult, 0, len(req.Targets))
	for _, t := range req.Targets {
		results = append(results, a.liftOne(t, rules, depthLimit))
	}
	return withLoad{results, a.load}, a.stats(), nil
}

func (a *qAnalysis) stats() *Stats {
	return &Stats{PackagesLoaded: a.npkgs, CallgraphNodes: len(a.g.nodes), CallgraphEdges: a.g.edgeCount()}
}

func (a *qAnalysis) liftOne(t Target, rules []string, depthLimit int) LiftResult {
	res := LiftResult{Target: t, Rules: map[string]LiftRuleResult{}, MatchedFunctions: []string{}}
	obj, ids, notInProgram, err := a.resolveSeed(t)
	if err != nil {
		res.Status, res.Error = LiftError, err
		return res
	}
	if notInProgram {
		res.Status, res.PackageNotInProgram = LiftNotInProgram, true
		return res
	}
	if isGenericDecl(obj) {
		res.Status = LiftError
		res.Error = errf(CodeUnsupportedForm, fmt.Sprintf("generic target %s: lifting generic functions is not supported", t.Symbol))
		return res
	}
	for _, id := range ids {
		res.MatchedFunctions = append(res.MatchedFunctions, a.g.nodes[id].Name())
	}
	sort.Strings(res.MatchedFunctions)
	if isEntryPoint(obj) {
		self := LiftEntry{Package: t.Package, Symbol: objSymbol(obj), Depth: 0,
			Path: CallPath{Entry: t, Target: t, Edges: []PathEdge{}}}
		for _, r := range rules {
			res.Rules[r] = LiftRuleResult{Entries: []LiftEntry{self}}
		}
		res.Status = LiftAlreadyExported
		return res
	}
	found := false
	for _, r := range rules {
		rr := a.walkUp(t, ids, r == RuleAll, depthLimit)
		res.Rules[r] = rr
		if len(rr.Entries) > 0 {
			found = true
		}
	}
	if found {
		res.Status = LiftLifted
	} else {
		res.Status = LiftRootOnly
	}
	return res
}

// walkUp is a breadth-first search over callers from the seed's nodes, limited to nodes of the
// loaded module. NEAREST (all=false) records an exported entry point and does not walk past it;
// ALL records it and keeps going. The example path of an entry is a shortest one.
func (a *qAnalysis) walkUp(t Target, seeds []int, all bool, depthLimit int) LiftRuleResult {
	rr := LiftRuleResult{Entries: []LiftEntry{}}
	dist := map[int]int{}
	next := map[int]gEdge{} // node -> the edge from it towards the seed
	var queue []int
	for _, s := range seeds {
		if _, ok := dist[s]; !ok {
			dist[s] = 0
			queue = append(queue, s)
		}
	}
	for len(queue) > 0 {
		n := queue[0]
		queue = queue[1:]
		if dist[n] > 0 && a.entry[n] {
			rr.Entries = append(rr.Entries, a.liftEntry(t, n, dist[n], next))
			if !all {
				continue
			}
		}
		if dist[n] >= depthLimit {
			for _, e := range a.in[n] {
				if _, seen := dist[e.From]; !seen && a.inModule[e.From] {
					rr.DepthLimitReached = true
				}
			}
			continue
		}
		for _, e := range a.in[n] {
			if !a.inModule[e.From] {
				continue
			}
			if _, seen := dist[e.From]; seen {
				continue
			}
			dist[e.From] = dist[n] + 1
			next[e.From] = e
			queue = append(queue, e.From)
		}
	}
	sort.SliceStable(rr.Entries, func(i, j int) bool {
		x, y := rr.Entries[i], rr.Entries[j]
		if x.Depth != y.Depth {
			return x.Depth < y.Depth
		}
		if x.Package != y.Package {
			return x.Package < y.Package
		}
		return x.Symbol < y.Symbol
	})
	rr.Entries = dedupeEntries(rr.Entries)
	return rr
}

// dedupeEntries keeps the first (shallowest) entry per (package, symbol): several graph nodes
// may implement one declaration.
func dedupeEntries(in []LiftEntry) []LiftEntry {
	seen := map[Target]bool{}
	out := in[:0]
	for _, e := range in {
		k := Target{Package: e.Package, Symbol: e.Symbol}
		if !seen[k] {
			seen[k] = true
			out = append(out, e)
		}
	}
	return out
}

func (a *qAnalysis) liftEntry(t Target, id, depth int, next map[int]gEdge) LiftEntry {
	et := a.entryTarget(id)
	le := LiftEntry{Package: et.Package, Symbol: et.Symbol, Depth: depth,
		Path: CallPath{Entry: et, Target: t, Edges: []PathEdge{}}}
	for n := id; ; {
		e, ok := next[n]
		if !ok {
			break
		}
		le.Path.Edges = append(le.Path.Edges, PathEdge{
			Caller: a.g.nodes[e.From].Name(), Callee: a.g.nodes[e.To].Name(), CallSite: e.Site, Kind: e.Kind})
		if e.Kind == KindDynamic {
			le.Dynamic = true
		}
		n = e.To
	}
	return le
}

func runCallers(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	return runNeighbors(req, stderr, true)
}

func runCallees(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	return runNeighbors(req, stderr, false)
}

func runNeighbors(req *Request, stderr io.Writer, callers bool) (any, *Stats, *Error) {
	a, err := loadQuery(req, stderr)
	if err != nil {
		return nil, nil, err
	}
	hops, maxResults := req.Limits.MaxHops, req.Limits.MaxResults
	if hops == 0 {
		hops = defaultMaxHops
	}
	if maxResults == 0 {
		maxResults = defaultMaxResults
	}
	results := make([]NeighborResult, 0, len(req.Targets))
	for _, t := range req.Targets {
		results = append(results, a.neighbors(t, callers, hops, maxResults, req.External))
	}
	return withLoad{results, a.load}, a.stats(), nil
}

func (a *qAnalysis) neighbors(t Target, callers bool, hops, maxResults int, external bool) NeighborResult {
	res := NeighborResult{Target: t, Edges: []HopEdge{}, MatchedFunctions: []string{}}
	_, ids, notInProgram, err := a.resolveSeed(t)
	switch {
	case err != nil:
		res.Result, res.Error = NeighborError, err
		return res
	case notInProgram:
		res.Result, res.PackageNotInProgram = NeighborNotInProgram, true
		return res
	}
	for _, id := range ids {
		res.MatchedFunctions = append(res.MatchedFunctions, a.g.nodes[id].Name())
	}
	sort.Strings(res.MatchedFunctions)
	seen := map[int]bool{}
	frontier := append([]int(nil), ids...)
	for _, id := range ids {
		seen[id] = true
	}
	for hop := 1; hop <= hops && len(frontier) > 0; hop++ {
		var nextFrontier []int
		for _, n := range frontier {
			edges := a.g.out[n]
			if callers {
				edges = a.in[n]
			}
			for _, e := range edges {
				far := e.To
				if callers {
					far = e.From
				}
				if !external && !a.inModule[far] {
					continue
				}
				if len(res.Edges) >= maxResults {
					res.Truncated = true
					continue
				}
				res.Edges = append(res.Edges, HopEdge{Hop: hop, Caller: a.g.nodes[e.From].Name(),
					Callee: a.g.nodes[e.To].Name(), CallSite: e.Site, Kind: e.Kind, Other: nodeTarget(a.g, far)})
				if !seen[far] {
					seen[far] = true
					nextFrontier = append(nextFrontier, far)
				}
			}
		}
		frontier = nextFrontier
	}
	if len(res.Edges) == 0 {
		res.Result = NeighborNone
	} else {
		res.Result = NeighborFound
	}
	return res
}
