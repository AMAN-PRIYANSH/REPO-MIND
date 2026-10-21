package main

import (
	"fmt"
	"go/types"
	"regexp"
	"strings"

	"golang.org/x/tools/go/ssa"
)

// symbolRef is a parsed vulndb-format symbol: "Func", "Type.Method".
// Pointer receivers ("*T.M", "(*T).M") and type parameters ("F[T]", "List[T].Push")
// are accepted and normalised away, because vulndb symbols carry neither.
type symbolRef struct {
	Recv    string // "" for package-level functions
	Name    string
	Generic bool // the input carried type parameters
}

var ident = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// parseSymbol parses a target symbol. It returns an UNSUPPORTED_SYMBOL_FORM error for anything else.
func parseSymbol(sym string) (symbolRef, *Error) {
	s := strings.TrimSpace(sym)
	bad := func() (symbolRef, *Error) {
		return symbolRef{}, errf(CodeUnsupportedForm, fmt.Sprintf("unrecognised symbol form: %q", sym))
	}
	generic := strings.ContainsAny(s, "[]")
	s, ok := stripTypeParams(s)
	if !ok {
		return bad()
	}
	if strings.HasPrefix(s, "(*") {
		// (*T).M
		end := strings.Index(s, ")")
		if end < 0 || !strings.HasPrefix(s[end:], ").") {
			return bad()
		}
		s = s[2:end] + "." + s[end+2:]
	}
	s = strings.TrimPrefix(s, "*")
	parts := strings.Split(s, ".")
	for _, p := range parts {
		if !ident.MatchString(p) {
			return bad()
		}
	}
	switch len(parts) {
	case 1:
		return symbolRef{Name: parts[0], Generic: generic}, nil
	case 2:
		return symbolRef{Recv: parts[0], Name: parts[1], Generic: generic}, nil
	}
	return bad()
}

// stripTypeParams removes every balanced [...] group. ok is false if brackets are unbalanced.
func stripTypeParams(s string) (string, bool) {
	var b strings.Builder
	depth := 0
	for _, r := range s {
		switch {
		case r == '[':
			depth++
		case r == ']':
			depth--
			if depth < 0 {
				return "", false
			}
		case depth == 0:
			b.WriteRune(r)
		}
	}
	return b.String(), depth == 0
}

func (r symbolRef) String() string {
	if r.Recv == "" {
		return r.Name
	}
	return r.Recv + "." + r.Name
}

// lookupTarget finds the declared function or method object for a target in the loaded program.
// A missing package or symbol is TARGET_NOT_FOUND, never NO_PATH.
func lookupTarget(prog *ssa.Program, t Target) (*types.Func, *Error) {
	ref, err := parseSymbol(t.Symbol)
	if err != nil {
		return nil, err
	}
	pkg := prog.ImportedPackage(t.Package)
	if pkg == nil {
		return nil, errf(CodeTargetNotFound, fmt.Sprintf("package %s is not part of the loaded program", t.Package))
	}
	return lookupInScope(pkg.Pkg, ref, t)
}

func lookupInScope(pkg *types.Package, ref symbolRef, t Target) (*types.Func, *Error) {
	notFound := errf(CodeTargetNotFound, fmt.Sprintf("symbol %s not found in package %s", t.Symbol, t.Package))
	if ref.Recv == "" {
		if fn, ok := pkg.Scope().Lookup(ref.Name).(*types.Func); ok {
			return fn, nil
		}
		return nil, notFound
	}
	tn, ok := pkg.Scope().Lookup(ref.Recv).(*types.TypeName)
	if !ok {
		return nil, notFound
	}
	named, ok := types.Unalias(tn.Type()).(*types.Named)
	if !ok {
		return nil, notFound
	}
	for i := 0; i < named.NumMethods(); i++ {
		if m := named.Method(i); m.Name() == ref.Name {
			return m, nil
		}
	}
	return nil, notFound
}

// isWrapper reports synthetic functions that only forward to another function.
// They carry the wrapped method's object, so they must not count as the target itself.
func isWrapper(fn *ssa.Function) bool {
	for _, p := range []string{"wrapper for ", "thunk for ", "bound method wrapper for ", "instantiation wrapper of "} {
		if strings.HasPrefix(fn.Synthetic, p) {
			return true
		}
	}
	return false
}

// declObject is the declared (origin) function object that fn implements, or nil.
func declObject(fn *ssa.Function) *types.Func {
	if isWrapper(fn) {
		return nil
	}
	f, ok := fn.Object().(*types.Func)
	if !ok {
		return nil
	}
	return f.Origin()
}

// funcPkgPath is the package path a function belongs to (for instances and wrappers too).
func funcPkgPath(fn *ssa.Function) string {
	if fn.Pkg != nil {
		return fn.Pkg.Pkg.Path()
	}
	if o := fn.Object(); o != nil && o.Pkg() != nil {
		return o.Pkg().Path()
	}
	if fn.Parent() != nil {
		return funcPkgPath(fn.Parent())
	}
	if recv := fn.Signature.Recv(); recv != nil {
		if n := namedOf(recv.Type()); n != nil && n.Obj().Pkg() != nil {
			return n.Obj().Pkg().Path()
		}
	}
	return ""
}

func namedOf(t types.Type) *types.Named {
	if p, ok := types.Unalias(t).(*types.Pointer); ok {
		t = p.Elem()
	}
	n, _ := types.Unalias(t).(*types.Named)
	return n
}

// funcSymbol is the vulndb-style symbol of an SSA function, extended for nodes vulndb never names:
// closures keep SSA's "$n" suffix, instances keep their type arguments, wrappers get a "$..." marker.
func funcSymbol(fn *ssa.Function) string {
	name := fn.Name()
	if fn.Parent() != nil {
		// Closure: "outer$1"; the outer function's symbol carries the receiver.
		if rest, ok := strings.CutPrefix(name, fn.Parent().Name()); ok {
			return funcSymbol(fn.Parent()) + rest
		}
		return funcSymbol(fn.Parent()) + "$" + name
	}
	switch {
	case strings.HasPrefix(fn.Synthetic, "wrapper for "):
		name += "$wrapper"
	case strings.HasPrefix(fn.Synthetic, "instantiation wrapper of "):
		name += "$instwrapper"
	}
	recv := fn.Signature.Recv()
	if recv == nil {
		// Bound-method wrappers and thunks take the receiver from the method they wrap.
		if m, ok := fn.Object().(*types.Func); ok {
			recv = m.Signature().Recv()
		}
	}
	if recv == nil {
		return name
	}
	n := namedOf(recv.Type())
	if n == nil {
		return name
	}
	return n.Obj().Name() + "." + name
}

// funcName is the CallPath edge form: "<package path>.<symbol>".
func funcName(fn *ssa.Function) string {
	if p := funcPkgPath(fn); p != "" {
		return p + "." + funcSymbol(fn)
	}
	return funcSymbol(fn)
}
