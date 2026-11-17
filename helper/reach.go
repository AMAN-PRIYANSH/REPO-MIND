package main

import (
	"fmt"
	"go/types"
	"io"
	"sort"

	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/cha"
	"golang.org/x/tools/go/callgraph/vta"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

// analysis is a loaded program with its VTA call graph in reduced form.
type analysis struct {
	prog  *ssa.Program
	g     *graph
	roots []int
	byObj map[*types.Func][]int // declared function -> graph nodes implementing it
	npkgs int
	// Kept for the CP9 feasibility filter (feasible.go); unused otherwise.
	cg   *callgraph.Graph
	fnOf []*ssa.Function // graph node id -> SSA function
	idOf map[*ssa.Function]int
	rel  relativizer
}

func analyse(req *Request, stderr io.Writer) (*analysis, *Error) {
	pkgs, dir, err := loadPackages(req, packages.LoadAllSyntax)
	if err != nil {
		return nil, err
	}
	prog, ssaPkgs := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()
	var rootFns []*ssa.Function
	for i, sp := range ssaPkgs {
		if sp == nil {
			return nil, errf(CodeLoadFailed, "no SSA package for "+pkgs[i].PkgPath)
		}
		mainFn := sp.Func("main")
		if mainFn == nil {
			return nil, errf(CodeLoadFailed, "package "+pkgs[i].PkgPath+" has no main function")
		}
		// The package initializer runs every imported package's init before main.
		if initFn := sp.Func("init"); initFn != nil {
			rootFns = append(rootFns, initFn)
		}
		rootFns = append(rootFns, mainFn)
	}
	cg := vtaCallGraph(prog, rootFns)
	a := &analysis{prog: prog, byObj: map[*types.Func][]int{}, npkgs: countPackages(pkgs), cg: cg, rel: newRelativizer(dir)}
	var r reduced
	a.g, a.roots, a.byObj, r = reduceFull(prog, cg, rootFns, a.rel)
	a.fnOf, a.idOf = r.fnOf, r.idOf
	fmt.Fprintf(stderr, "vt-helper: %d packages, %d call-graph nodes, %d edges\n", a.npkgs, len(a.g.nodes), a.g.edgeCount())
	return a, nil
}

// vtaCallGraph follows govulncheck: a CHA graph seeds VTA over the functions CHA can reach
// from the roots, and a second VTA pass refines over what the first can reach.
func vtaCallGraph(prog *ssa.Program, roots []*ssa.Function) *callgraph.Graph {
	initial := cha.CallGraph(prog)
	fs := forwardSlice(roots, initial)
	first := vta.CallGraph(fs, initial)
	fs = forwardSlice(roots, first)
	return vta.CallGraph(fs, first)
}

func forwardSlice(roots []*ssa.Function, cg *callgraph.Graph) map[*ssa.Function]bool {
	seen := map[*ssa.Function]bool{}
	var stack []*ssa.Function
	for _, r := range roots {
		if !seen[r] {
			seen[r] = true
			stack = append(stack, r)
		}
	}
	for len(stack) > 0 {
		fn := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		n := cg.Nodes[fn]
		if n == nil {
			continue
		}
		for _, e := range n.Out {
			if !seen[e.Callee.Func] {
				seen[e.Callee.Func] = true
				stack = append(stack, e.Callee.Func)
			}
		}
	}
	return seen
}

// reduced maps graph node ids back to SSA functions (CP9).
type reduced struct {
	fnOf []*ssa.Function
	idOf map[*ssa.Function]int
}

// edgeSiteKind is the call site and kind of an SSA call-graph edge, as stored in the reduced graph.
func edgeSiteKind(prog *ssa.Program, rel relativizer, e *callgraph.Edge) (Site, string) {
	site, kind := Site{}, KindStatic
	if e.Site != nil {
		pos := prog.Fset.Position(e.Site.Pos())
		site = Site{File: rel.file(pos.Filename), Line: pos.Line}
		if e.Site.Common().StaticCallee() == nil {
			kind = KindDynamic
		}
	}
	return site, kind
}

// reduceFull converts an SSA call graph into a graph, keeping only what is reachable from roots,
// and returns the node -> function mapping as well.
func reduceFull(prog *ssa.Program, cg *callgraph.Graph, rootFns []*ssa.Function, rel relativizer) (*graph, []int, map[*types.Func][]int, reduced) {
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
	reachable := forwardSlice(rootFns, cg)
	fns := make([]*ssa.Function, 0, len(reachable))
	for fn := range reachable {
		fns = append(fns, fn)
	}
	// Visit in a fixed order so that keys (and so tie-breaks) are deterministic.
	sort.Slice(fns, func(i, j int) bool { return keyOf(fns[i]) < keyOf(fns[j]) })
	for _, fn := range fns {
		from := add(fn)
		n := cg.Nodes[fn]
		if n == nil {
			continue
		}
		for _, e := range n.Out {
			site, kind := edgeSiteKind(prog, rel, e)
			b.edge(from, add(e.Callee.Func), site, kind)
		}
	}
	g, ids := b.freeze()
	var roots []int
	for _, r := range rootFns {
		roots = append(roots, ids[keyOf(r)])
	}
	byObj := map[*types.Func][]int{}
	for _, fn := range fns {
		if obj := declObject(fn); obj != nil {
			byObj[obj] = append(byObj[obj], ids[keyOf(fn)])
		}
	}
	for _, v := range byObj {
		sort.Ints(v)
	}
	r := reduced{fnOf: make([]*ssa.Function, len(g.nodes)), idOf: make(map[*ssa.Function]int, len(keys))}
	for fn, k := range keys {
		if id, ok := ids[k]; ok {
			r.fnOf[id], r.idOf[fn] = fn, id
		}
	}
	return g, roots, byObj, r
}

func (a *analysis) stats() *Stats {
	return &Stats{PackagesLoaded: a.npkgs, CallgraphNodes: len(a.g.nodes), CallgraphEdges: a.g.edgeCount()}
}

func runReach(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	a, err := analyse(req, stderr)
	if err != nil {
		return nil, nil, err
	}
	results := make([]TargetResult, 0, len(req.Targets))
	targetIDs := make([][]int, 0, len(req.Targets))
	for _, t := range req.Targets {
		obj, notInProgram, terr := lookupTarget(a.prog, t)
		targetIDs = append(targetIDs, nil)
		if terr != nil {
			results = append(results, TargetResult{Target: t, Result: ResultError, Paths: []CallPath{},
				MatchedFunctions: []string{}, Error: terr})
			continue
		}
		if notInProgram {
			results = append(results, TargetResult{Target: t, Result: ResultNoPath, Paths: []CallPath{},
				MatchedFunctions: []string{}, PackageNotInProgram: true})
			continue
		}
		targetIDs[len(targetIDs)-1] = a.byObj[obj]
		results = append(results, targetResult(a.g, t, a.roots, a.byObj[obj], req.Limits))
	}
	stats := a.stats()
	if req.Feasibility != nil {
		// CP9: runs after the unchanged path search; it only annotates PATH_FOUND results.
		stats.Feasibility = applyFeasibility(a, req, results, targetIDs)
	}
	return results, stats, nil
}

func runEdges(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	a, err := analyse(req, stderr)
	if err != nil {
		return nil, nil, err
	}
	return checkEdges(a.g, req.Edges), a.stats(), nil
}

// checkEdges answers edge queries against a graph by full function name.
func checkEdges(g *graph, queries []EdgeQuery) []EdgeResult {
	out := make([]EdgeResult, 0, len(queries))
	for _, q := range queries {
		r := EdgeResult{Caller: q.Caller, Callee: q.Callee, CallSite: q.CallSite, CallSites: []Site{}, Kinds: []string{}}
		callers, callees := g.index[q.Caller], g.index[q.Callee]
		r.CallerFound, r.CalleeFound = len(callers) > 0, len(callees) > 0
		want := map[int]bool{}
		for _, id := range callees {
			want[id] = true
		}
		for _, c := range callers {
			for _, e := range g.out[c] {
				if want[e.To] && (q.CallSite == nil || *q.CallSite == e.Site) {
					r.CallSites = append(r.CallSites, e.Site)
					r.Kinds = append(r.Kinds, e.Kind)
				}
			}
		}
		r.Exists = len(r.CallSites) > 0
		out = append(out, r)
	}
	return out
}
