package main

import (
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"sort"
	"testing"

	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

func TestParseSymbol(t *testing.T) {
	ok := map[string]symbolRef{
		"Parse":              {Name: "Parse"},
		" Parse ":            {Name: "Parse"},
		"Impl.Run":           {Recv: "Impl", Name: "Run"},
		"*PImpl.Run":         {Recv: "PImpl", Name: "Run"},
		"(*PImpl).Run":       {Recv: "PImpl", Name: "Run"},
		"ParseAny[T]":        {Name: "ParseAny", Generic: true},
		"List[K, V].Push":    {Recv: "List", Name: "Push", Generic: true},
		"(*List[T]).Push":    {Recv: "List", Name: "Push", Generic: true},
		"Map[K comparable]":  {Name: "Map", Generic: true},
		"Nested[T[int]].Get": {Recv: "Nested", Name: "Get", Generic: true},
	}
	for in, want := range ok {
		got, err := parseSymbol(in)
		if err != nil || got != want {
			t.Errorf("parseSymbol(%q) = %+v, %v; want %+v", in, got, err, want)
		}
	}
	for _, in := range []string{"", "a.b.c", "F[", "F]", "1x", "(*T)M", "(*T.M", "T.", ".M", "pkg/F"} {
		if _, err := parseSymbol(in); err == nil || err.Code != CodeUnsupportedForm {
			t.Errorf("parseSymbol(%q) = %v; want %s", in, err, CodeUnsupportedForm)
		}
	}
}

const matchSrc = `package p

type T struct{}

func (T) M() int { return 1 }

type P struct{}

func (*P) M() int { return 2 }

type L[E any] struct{ e E }

func (l *L[E]) Push(e E) { l.e = e }

func G[X any](x X) X { return x }

func F() int { return 0 }

type I interface{ M() int }

func Use() {
	var i I = T{}      // T.M through an interface: (*T).M wrapper may be created
	_ = i.M()
	f := T{}.M         // bound method wrapper T.M$bound
	_ = f()
	g := T.M           // method expression (thunk or direct)
	_ = g(T{})
	h := (*P).M
	_ = h(&P{})
	_ = G[int](1)
	_ = G[string]("")
	var l L[int]
	l.Push(1)
	c := func() int { return F() } // closure Use$1
	_ = c()
}
`

func buildMatchProgram(t *testing.T) (*ssa.Program, *types.Package) {
	t.Helper()
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "p.go", matchSrc, 0)
	if err != nil {
		t.Fatal(err)
	}
	pkg := types.NewPackage("example.com/p", "p")
	ssaPkg, _, err := ssautil.BuildPackage(&types.Config{Importer: importer.Default()}, fset, pkg, []*ast.File{f}, ssa.InstantiateGenerics)
	if err != nil {
		t.Fatal(err)
	}
	return ssaPkg.Prog, pkg
}

// matching returns the names of all SSA functions whose declared object is the target's.
func matching(t *testing.T, prog *ssa.Program, pkg *types.Package, sym string) []string {
	t.Helper()
	ref, perr := parseSymbol(sym)
	if perr != nil {
		t.Fatal(perr)
	}
	obj, lerr := lookupInScope(pkg, ref, Target{Package: pkg.Path(), Symbol: sym})
	if lerr != nil {
		t.Fatalf("%s: %v", sym, lerr)
	}
	var names []string
	for fn := range ssautil.AllFunctions(prog) {
		if declObject(fn) == obj {
			names = append(names, funcName(fn))
		}
	}
	sort.Strings(names)
	return names
}

func TestTargetMatchingExcludesWrappersAndIncludesInstances(t *testing.T) {
	prog, pkg := buildMatchProgram(t)
	cases := map[string][]string{
		"F":            {"example.com/p.F"},
		"T.M":          {"example.com/p.T.M"},
		"P.M":          {"example.com/p.P.M"},
		"(*P).M":       {"example.com/p.P.M"},
		"G":            {"example.com/p.G", "example.com/p.G[int]", "example.com/p.G[string]"}, // origin and instances
		"G[X]":         {"example.com/p.G", "example.com/p.G[int]", "example.com/p.G[string]"},
		"L.Push":       {"example.com/p.L.Push[int]"},
		"(*L[E]).Push": {"example.com/p.L.Push[int]"},
	}
	for sym, want := range cases {
		got := matching(t, prog, pkg, sym)
		if len(got) != len(want) {
			t.Errorf("%s: matched %v; want %v", sym, got, want)
			continue
		}
		for i := range got {
			if got[i] != want[i] {
				t.Errorf("%s: matched %v; want %v", sym, got, want)
			}
		}
	}
}

func TestTargetNotFound(t *testing.T) {
	_, pkg := buildMatchProgram(t)
	for _, sym := range []string{"Nope", "T.Nope", "Nope.M", "I"} {
		ref, _ := parseSymbol(sym)
		if _, err := lookupInScope(pkg, ref, Target{Package: pkg.Path(), Symbol: sym}); err == nil || err.Code != CodeTargetNotFound {
			t.Errorf("%s: got %v; want %s", sym, err, CodeTargetNotFound)
		}
	}
}

func TestFuncNamesOfSyntheticFunctions(t *testing.T) {
	prog, _ := buildMatchProgram(t)
	names := map[string]bool{}
	for fn := range ssautil.AllFunctions(prog) {
		names[funcName(fn)] = true
	}
	for _, want := range []string{"example.com/p.T.M$bound", "example.com/p.Use$1", "example.com/p.init"} {
		if !names[want] {
			t.Errorf("missing function name %q", want)
		}
	}
	// A wrapper must never be named like the method it wraps.
	for fn := range ssautil.AllFunctions(prog) {
		if isWrapper(fn) && (funcName(fn) == "example.com/p.T.M" || funcName(fn) == "example.com/p.P.M") {
			t.Errorf("wrapper %s (%s) has the wrapped method's name", fn, fn.Synthetic)
		}
	}
}
