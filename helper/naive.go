package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io"
	"path"
	"sort"
	"strconv"

	"golang.org/x/tools/go/packages"
)

// The naive control (R1): a call graph built from go/ast with names only, no types.
//
//   - f(...)        -> the package-level function f of the same package
//   - pkg.F(...)    -> function F of the imported package (import name resolved from the file)
//   - x.M(...)      -> every method named M in every analysed package (marked DYNAMIC)
//
// Calls inside function literals are attributed to the enclosing declaration. Calls through
// function values, method values or expressions, and reflection produce no edge. Only
// packages outside the standard library are parsed. Roots are main and every init.
func runNaive(req *Request, stderr io.Writer) (any, *Stats, *Error) {
	mode := packages.NeedName | packages.NeedFiles | packages.NeedImports | packages.NeedDeps | packages.NeedModule
	pkgs, dir, err := loadPackages(req, mode)
	if err != nil {
		return nil, nil, err
	}
	ng, perr := buildNaive(pkgs, newRelativizer(dir))
	if perr != nil {
		return nil, nil, perr
	}
	fmt.Fprintf(stderr, "vt-helper: naive graph over %d packages, %d nodes, %d edges\n", len(ng.parsed), len(ng.g.nodes), ng.g.edgeCount())
	results := make([]TargetResult, 0, len(req.Targets))
	for _, t := range req.Targets {
		ids, terr := ng.lookup(t)
		if terr != nil {
			results = append(results, TargetResult{Target: t, Result: ResultError, Paths: []CallPath{},
				MatchedFunctions: []string{}, Error: terr})
			continue
		}
		results = append(results, targetResult(ng.g, t, ng.roots, ids, req.Limits))
	}
	return results, &Stats{PackagesLoaded: countPackages(pkgs), CallgraphNodes: len(ng.g.nodes), CallgraphEdges: ng.g.edgeCount()}, nil
}

type naiveGraph struct {
	g      *graph
	roots  []int
	parsed map[string]bool
}

type naiveFile struct {
	pkg     *packages.Package
	file    *ast.File
	imports map[string]string // local name -> import path
}

func buildNaive(roots []*packages.Package, rel relativizer) (*naiveGraph, *Error) {
	var all []*packages.Package
	packages.Visit(roots, nil, func(p *packages.Package) {
		if p.Module != nil { // standard-library packages have no module
			all = append(all, p)
		}
	})
	sort.Slice(all, func(i, j int) bool { return all[i].PkgPath < all[j].PkgPath })
	fset := token.NewFileSet()
	b := newGraphBuilder()
	ng := &naiveGraph{parsed: map[string]bool{}}
	funcs := map[string]map[string]int{} // pkg path -> symbol -> node
	methods := map[string][]int{}        // method name -> nodes
	type decl struct {
		id int
		fd *ast.FuncDecl
		nf *naiveFile
	}
	var decls []decl
	var rootIDs []int
	for _, p := range all {
		ng.parsed[p.PkgPath] = true
		funcs[p.PkgPath] = map[string]int{}
		inits := 0
		for _, name := range p.GoFiles {
			f, err := parser.ParseFile(fset, name, nil, parser.SkipObjectResolution)
			if err != nil {
				return nil, errf(CodeLoadFailed, "cannot parse "+name+": "+err.Error())
			}
			nf := &naiveFile{pkg: p, file: f, imports: map[string]string{}}
			for _, is := range f.Imports {
				ip, _ := strconv.Unquote(is.Path.Value)
				local := path.Base(ip)
				if imp := p.Imports[ip]; imp != nil && imp.Name != "" {
					local = imp.Name
				}
				if is.Name != nil {
					local = is.Name.Name
				}
				nf.imports[local] = ip
			}
			for _, d := range f.Decls {
				fd, ok := d.(*ast.FuncDecl)
				if !ok || fd.Body == nil {
					continue
				}
				sym := declSymbol(fd)
				if fd.Recv == nil && sym == "init" {
					inits++
					sym = fmt.Sprintf("init#%d", inits)
				}
				id := b.node(p.PkgPath+"\x00"+sym, node{Pkg: p.PkgPath, Sym: sym})
				decls = append(decls, decl{id, fd, nf})
				if fd.Recv != nil {
					methods[fd.Name.Name] = append(methods[fd.Name.Name], id)
				} else {
					funcs[p.PkgPath][sym] = id
				}
				if fd.Recv == nil && (sym == "main" && p.Name == "main" || fd.Name.Name == "init") {
					rootIDs = append(rootIDs, id)
				}
			}
		}
	}
	for _, d := range decls {
		ast.Inspect(d.fd.Body, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			pos := fset.Position(call.Lparen)
			site := Site{File: rel.file(pos.Filename), Line: pos.Line}
			switch fun := unwrapCallee(call.Fun).(type) {
			case *ast.Ident:
				if id, ok := funcs[d.nf.pkg.PkgPath][fun.Name]; ok {
					b.edge(d.id, id, site, KindStatic)
				}
			case *ast.SelectorExpr:
				if x, ok := fun.X.(*ast.Ident); ok {
					if ip, ok := d.nf.imports[x.Name]; ok {
						if id, ok := funcs[ip][fun.Sel.Name]; ok {
							b.edge(d.id, id, site, KindStatic)
						}
						return true
					}
				}
				for _, id := range methods[fun.Sel.Name] {
					b.edge(d.id, id, site, KindDynamic)
				}
			}
			return true
		})
	}
	g, ids := b.freeze()
	ng.g = g
	for _, r := range rootIDs {
		ng.roots = append(ng.roots, ids[b.keys[r]])
	}
	sort.Ints(ng.roots)
	return ng, nil
}

func unwrapCallee(e ast.Expr) ast.Expr {
	for {
		switch t := e.(type) {
		case *ast.ParenExpr:
			e = t.X
		case *ast.IndexExpr:
			e = t.X
		case *ast.IndexListExpr:
			e = t.X
		default:
			return e
		}
	}
}

// lookup finds the graph nodes declared for a target. A target that is not declared in any
// parsed package is TARGET_NOT_FOUND.
func (ng *naiveGraph) lookup(t Target) ([]int, *Error) {
	ref, err := parseSymbol(t.Symbol)
	if err != nil {
		return nil, err
	}
	if !ng.parsed[t.Package] {
		return nil, errf(CodeTargetNotFound, fmt.Sprintf("package %s is not part of the loaded program", t.Package))
	}
	ids := ng.g.index[t.Package+"."+ref.String()]
	if len(ids) == 0 {
		return nil, errf(CodeTargetNotFound, fmt.Sprintf("symbol %s not found in package %s", t.Symbol, t.Package))
	}
	return ids, nil
}
