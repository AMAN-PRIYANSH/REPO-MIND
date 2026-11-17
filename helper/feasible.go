package main

// CP9: path-feasibility filter for reach (docs/implementation/checkpoints/CP9.md).
//
// The filter runs on the unchanged VTA graph, after the path search. It recognises three
// specific reasons why a call-graph step cannot run, and nothing else:
//
//	F1  a dynamic call (interface method or function value) on a value that came in through a
//	    parameter, where the value passed on this path has another dynamic type or is another
//	    function than the callee of this step (VTA is context-insensitive and joins callers);
//	F2  the step's call site runs only under a branch on a parameter, and the constant passed on
//	    this path makes the branch go the other way;
//	F3  the step's call site runs only under a test of a struct field (x.f != nil, x.f != 0, ...)
//	    and no code in the analysed program ever assigns that field.
//
// Context: the facts that make F1 and F2 decidable are the arguments of the call site that
// entered the function, followed back through direct parameter pass-through along the same
// path (Once.Do(f) -> doSlow(f) -> f() needs two levels). Everything else is unknown, and an
// unknown value never makes a step infeasible.
//
// Decision: a breadth-first search over states (function, facts about its parameters) from the
// roots finds whether any path to the target avoids every infeasible step. Only when none does
// is the target INFEASIBLE. The N shortest raw paths are also examined one by one, and each
// one's first infeasible step is reported as the explanation (N = max_examined_paths).
// Downgrade-only: the filter never adds a path or removes a NO_PATH; Python turns INFEASIBLE
// into CANT_DETERMINE (PATHS_INFEASIBLE), never NOT_REACHABLE.

import (
	"container/heap"
	"fmt"
	"go/constant"
	"go/token"
	"go/types"
	"sort"
	"strings"
	"time"

	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
	"golang.org/x/tools/go/types/typeutil"
)

// Feasibility statuses, patterns and limits.
const (
	FeasFeasible   = "FEASIBLE"
	FeasInfeasible = "INFEASIBLE"
	FeasUndecided  = "UNDECIDED"

	PatF1 = "F1"
	PatF2 = "F2"
	PatF3 = "F3"

	EvidenceExamined = "EXAMINED_PATH"
	EvidenceSearch   = "STATE_SEARCH"

	UndecidedStateLimit   = "STATE_LIMIT"   // the state search hit max_states before it finished
	UndecidedContextLimit = "CONTEXT_LIMIT" // the target was reached only through merged (approximate) states
	UndecidedInconsistent = "INCONSISTENT"  // internal guard: search and path check disagree

	defaultMaxExamined = 20
	defaultMaxStates   = 4000000
	defaultMaxContexts = 64
	maxEnumPops        = 200000 // work cap of the N-shortest-paths enumeration
	maxWrapperDepth    = 3
)

type FeasibilityRequest struct {
	MaxExaminedPaths   int `json:"max_examined_paths"`
	MaxStates          int `json:"max_states"`
	MaxContextsPerNode int `json:"max_contexts_per_node"`
}

// InfeasibleStep is the first step of a path that cannot run, with the edges that carry the
// context it depends on (from the call site that created the value to the step, exclusive).
type InfeasibleStep struct {
	Pattern      string     `json:"pattern"`
	EdgeIndex    int        `json:"edge_index"`
	Edge         PathEdge   `json:"edge"`
	ContextEdges []PathEdge `json:"context_edges"`
	Reason       string     `json:"reason"`
}

type ExaminedPath struct {
	Length          int             `json:"length"`
	FirstInfeasible *InfeasibleStep `json:"first_infeasible"`
}

type FeasibilityResult struct {
	Status            string         `json:"status"`
	MaxExaminedPaths  int            `json:"max_examined_paths"`
	Examined          []ExaminedPath `json:"examined"`
	ExaminedTruncated bool           `json:"examined_truncated"`
	EvidencePath      *CallPath      `json:"evidence_path"`
	EvidenceSource    *string        `json:"evidence_source"`
	UndecidedReason   *string        `json:"undecided_reason"`
}

type FeasibilityStats struct {
	States              int   `json:"states"`
	ApproximateStates   int   `json:"approximate_states"`
	NodesOverContextCap int   `json:"nodes_over_context_cap"`
	StateLimitHit       bool  `json:"state_limit_hit"`
	MaxExaminedPaths    int   `json:"max_examined_paths"`
	MaxStates           int   `json:"max_states"`
	MaxContextsPerNode  int   `json:"max_contexts_per_node"`
	FieldIndexFunctions int   `json:"field_index_functions"`
	DurationMS          int64 `json:"duration_ms"`
}

func (r *FeasibilityRequest) withDefaults() FeasibilityRequest {
	out := *r
	if out.MaxExaminedPaths <= 0 {
		out.MaxExaminedPaths = defaultMaxExamined
	}
	if out.MaxStates <= 0 {
		out.MaxStates = defaultMaxStates
	}
	if out.MaxContextsPerNode <= 0 {
		out.MaxContextsPerNode = defaultMaxContexts
	}
	return out
}

// ---------------------------------------------------------------------------------------------
// Facts about parameter values.

type factKind uint8

const (
	fkType  factKind = iota + 1 // an interface value whose dynamic type is exactly typ
	fkFunc                      // a function value that is exactly fn
	fkConst                     // a constant (val), or the nil value of a nilable type (isNil)
	fkLen                       // a slice of known length n (variadic packing)
)

type fact struct {
	kind   factKind
	typ    types.Type
	fn     *ssa.Function
	val    constant.Value
	isNil  bool
	ctyp   types.Type
	n      int64
	origin int // path edge index whose call site created the value; -1 in the state search
}

// ctxMap holds known facts per parameter index of the function a state is in.
type ctxMap map[int]fact

// ---------------------------------------------------------------------------------------------

type edgeRef struct{ from, idx int }

type feas struct {
	prog     *ssa.Program
	g        *graph
	roots    []int
	fnOf     []*ssa.Function
	instrOut [][][]ssa.CallInstruction // aligned with g.out
	in       [][]edgeRef
	rel      []map[int]bool // relevant parameter indices per node
	pidx     map[*ssa.Parameter]int
	guards   map[ssa.CallInstruction][]guard
	types    typeutil.Map
	ntypes   int
	fields   *fieldIndex
	lim      FeasibilityRequest
	stats    FeasibilityStats

	// state search
	ctxs     []ctxMap
	ctxIndex map[string]int32
	states   []stRec
	seen     map[uint64]int32
	firstAt  map[int]int32 // node -> first exact state
	approxAt map[int]int32 // node -> first approximate state
	aborted  bool
}

type guard struct {
	cond ssa.Value
	want bool
}

type stRec struct {
	node, ctx  int32
	approx     bool
	pred, edge int32 // predecessor state and edge index in g.out[pred.node]; pred -1 for roots
}

func newFeas(a *analysis, req *FeasibilityRequest) *feas {
	fa := &feas{prog: a.prog, g: a.g, roots: a.roots, fnOf: a.fnOf, lim: req.withDefaults(),
		pidx: map[*ssa.Parameter]int{}, guards: map[ssa.CallInstruction][]guard{}}
	fa.stats.MaxExaminedPaths, fa.stats.MaxStates, fa.stats.MaxContextsPerNode =
		fa.lim.MaxExaminedPaths, fa.lim.MaxStates, fa.lim.MaxContextsPerNode
	for _, fn := range a.fnOf {
		if fn == nil {
			continue
		}
		for i, p := range fn.Params {
			fa.pidx[p] = i
		}
	}
	fa.mapInstructions(a)
	fa.computeRelevance()
	return fa
}

// mapInstructions attaches the SSA call instructions to each reduced edge (several instructions on
// one line share an edge) and builds the reverse adjacency.
func (fa *feas) mapInstructions(a *analysis) {
	g := fa.g
	fa.instrOut = make([][][]ssa.CallInstruction, len(g.nodes))
	fa.in = make([][]edgeRef, len(g.nodes))
	pos := make([]map[gEdge]int, len(g.nodes))
	for from, es := range g.out {
		fa.instrOut[from] = make([][]ssa.CallInstruction, len(es))
		pos[from] = make(map[gEdge]int, len(es))
		for i, e := range es {
			pos[from][e] = i
			fa.in[e.To] = append(fa.in[e.To], edgeRef{from, i})
		}
	}
	for from, fn := range fa.fnOf {
		if fn == nil {
			continue
		}
		n := a.cg.Nodes[fn]
		if n == nil {
			continue
		}
		for _, e := range n.Out {
			to, ok := a.idOf[e.Callee.Func]
			if !ok || e.Site == nil {
				continue
			}
			site, kind := edgeSiteKind(a.prog, a.rel, e)
			if i, ok := pos[from][gEdge{From: from, To: to, Site: site, Kind: kind}]; ok {
				fa.instrOut[from][i] = appendUnique(fa.instrOut[from][i], e.Site)
			}
		}
	}
}

func appendUnique(xs []ssa.CallInstruction, x ssa.CallInstruction) []ssa.CallInstruction {
	for _, y := range xs {
		if y == x {
			return xs
		}
	}
	return append(xs, x)
}

// ---------------------------------------------------------------------------------------------
// SSA helpers.

func callArgs(c ssa.CallInstruction) []ssa.Value {
	common := c.Common()
	if common.IsInvoke() {
		return append([]ssa.Value{common.Value}, common.Args...)
	}
	return common.Args
}

// strip removes conversions that keep the value (and so its dynamic type) unchanged.
func strip(v ssa.Value) ssa.Value {
	for {
		switch x := v.(type) {
		case *ssa.ChangeInterface:
			v = x.X
		case *ssa.ChangeType:
			v = x.X
		default:
			return v
		}
	}
}

func (fa *feas) paramOf(v ssa.Value, fn *ssa.Function) int {
	if p, ok := v.(*ssa.Parameter); ok && p.Parent() == fn {
		if i, ok := fa.pidx[p]; ok {
			return i
		}
	}
	return -1
}

func isLenCall(v ssa.Value) (ssa.Value, bool) {
	c, ok := v.(*ssa.Call)
	if !ok || c.Call.IsInvoke() {
		return nil, false
	}
	if b, ok := c.Call.Value.(*ssa.Builtin); ok && b.Name() == "len" && len(c.Call.Args) == 1 {
		return c.Call.Args[0], true
	}
	return nil, false
}

// condParams adds every parameter a condition reads in a form the evaluator understands.
func (fa *feas) condParams(v ssa.Value, fn *ssa.Function, out map[int]bool, depth int) {
	if depth > 8 {
		return
	}
	v = strip(v)
	if i := fa.paramOf(v, fn); i >= 0 {
		out[i] = true
		return
	}
	switch x := v.(type) {
	case *ssa.BinOp:
		fa.condParams(x.X, fn, out, depth+1)
		fa.condParams(x.Y, fn, out, depth+1)
	case *ssa.UnOp:
		if x.Op == token.NOT {
			fa.condParams(x.X, fn, out, depth+1)
		}
	case *ssa.Call:
		if arg, ok := isLenCall(x); ok {
			fa.condParams(arg, fn, out, depth+1)
		}
	}
}

// computeRelevance finds, per node, the parameters whose value can decide F1 or F2 in the function
// itself or, through pass-through, in a callee.
func (fa *feas) computeRelevance() {
	fa.rel = make([]map[int]bool, len(fa.g.nodes))
	var work []int
	for id, fn := range fa.fnOf {
		if fn == nil || len(fn.Params) == 0 {
			continue
		}
		direct := map[int]bool{}
		for _, b := range fn.Blocks {
			for _, ins := range b.Instrs {
				switch x := ins.(type) {
				case ssa.CallInstruction:
					if x.Common().StaticCallee() == nil {
						if i := fa.paramOf(strip(x.Common().Value), fn); i >= 0 {
							direct[i] = true
						}
					}
				case *ssa.If:
					fa.condParams(x.Cond, fn, direct, 0)
				}
			}
		}
		if len(direct) > 0 {
			fa.rel[id] = direct
			work = append(work, id)
		}
	}
	for len(work) > 0 {
		to := work[len(work)-1]
		work = work[:len(work)-1]
		callee := fa.fnOf[to]
		if callee == nil {
			continue
		}
		for _, r := range fa.in[to] {
			caller := fa.fnOf[r.from]
			if caller == nil {
				continue
			}
			for _, c := range fa.instrOut[r.from][r.idx] {
				args := callArgs(c)
				if len(args) != len(callee.Params) {
					continue
				}
				for j := range fa.rel[to] {
					if i := fa.paramOf(strip(args[j]), caller); i >= 0 {
						if fa.rel[r.from] == nil {
							fa.rel[r.from] = map[int]bool{}
						}
						if !fa.rel[r.from][i] {
							fa.rel[r.from][i] = true
							work = append(work, r.from)
						}
					}
				}
			}
		}
	}
}

// guardsOf returns the branch outcomes a call site needs: for every block X that dominates the call's
// block and has a single predecessor P ending in `if cond`, the edge P -> X must be taken.
func (fa *feas) guardsOf(c ssa.CallInstruction) []guard {
	if gs, ok := fa.guards[c]; ok {
		return gs
	}
	var gs []guard
	for x := c.Block(); x != nil; x = x.Idom() {
		if len(x.Preds) != 1 {
			continue
		}
		p := x.Preds[0]
		if p == x || len(p.Instrs) == 0 || len(p.Succs) != 2 || p.Succs[0] == p.Succs[1] {
			continue
		}
		if iff, ok := p.Instrs[len(p.Instrs)-1].(*ssa.If); ok {
			gs = append(gs, guard{cond: iff.Cond, want: p.Succs[0] == x})
		}
	}
	fa.guards[c] = gs
	return gs
}

// ---------------------------------------------------------------------------------------------
// Facts at a call site.

func nilable(t types.Type) bool {
	switch t.Underlying().(type) {
	case *types.Pointer, *types.Interface, *types.Slice, *types.Map, *types.Chan, *types.Signature:
		return true
	}
	return false
}

func zeroConst(t types.Type) (constant.Value, bool) {
	b, ok := t.Underlying().(*types.Basic)
	if !ok {
		return nil, false
	}
	switch {
	case b.Info()&types.IsBoolean != 0:
		return constant.MakeBool(false), true
	case b.Info()&types.IsString != 0:
		return constant.MakeString(""), true
	case b.Info()&(types.IsInteger|types.IsFloat) != 0:
		return constant.MakeInt64(0), true
	}
	return nil, false
}

func hasTypeParam(t types.Type) bool {
	found := false
	var walk func(t types.Type, depth int)
	walk = func(t types.Type, depth int) {
		if found || depth > 10 || t == nil {
			return
		}
		switch x := types.Unalias(t).(type) {
		case *types.TypeParam:
			found = true
		case *types.Pointer:
			walk(x.Elem(), depth+1)
		case *types.Slice:
			walk(x.Elem(), depth+1)
		case *types.Array:
			walk(x.Elem(), depth+1)
		case *types.Map:
			walk(x.Key(), depth+1)
			walk(x.Elem(), depth+1)
		case *types.Chan:
			walk(x.Elem(), depth+1)
		case *types.Named:
			if ta := x.TypeArgs(); ta != nil {
				for i := 0; i < ta.Len(); i++ {
					walk(ta.At(i), depth+1)
				}
			}
		}
	}
	walk(t, 0)
	return found
}

// factOf evaluates an argument at a call site in fn under ctx; ok is false when unknown.
func (fa *feas) factOf(v ssa.Value, fn *ssa.Function, ctx ctxMap, origin int) (fact, bool) {
	v = strip(v)
	if i := fa.paramOf(v, fn); i >= 0 {
		f, ok := ctx[i]
		return f, ok
	}
	switch x := v.(type) {
	case *ssa.MakeInterface:
		t := x.X.Type()
		if types.IsInterface(t) || hasTypeParam(t) {
			return fact{}, false
		}
		return fact{kind: fkType, typ: t, origin: origin}, true
	case *ssa.Function:
		return fact{kind: fkFunc, fn: x, origin: origin}, true
	case *ssa.MakeClosure:
		if f, ok := x.Fn.(*ssa.Function); ok {
			return fact{kind: fkFunc, fn: f, origin: origin}, true
		}
	case *ssa.Const:
		t := x.Type()
		if hasTypeParam(t) {
			return fact{}, false
		}
		if x.Value != nil {
			return fact{kind: fkConst, val: x.Value, ctyp: t, origin: origin}, true
		}
		if nilable(t) {
			return fact{kind: fkConst, isNil: true, ctyp: t, origin: origin}, true
		}
		if z, ok := zeroConst(t); ok {
			return fact{kind: fkConst, val: z, ctyp: t, origin: origin}, true
		}
	case *ssa.Slice:
		if x.Low == nil && x.High == nil && x.Max == nil {
			if al, ok := x.X.(*ssa.Alloc); ok {
				if pt, ok := al.Type().Underlying().(*types.Pointer); ok {
					if arr, ok := pt.Elem().Underlying().(*types.Array); ok {
						return fact{kind: fkLen, n: arr.Len(), origin: origin}, true
					}
				}
			}
		}
	}
	return fact{}, false
}

// childCtx is the callee's context after a call instruction (only relevant parameters are kept).
func (fa *feas) childCtx(to int, caller *ssa.Function, c ssa.CallInstruction, ctx ctxMap, origin int) ctxMap {
	callee := fa.fnOf[to]
	rel := fa.rel[to]
	if callee == nil || len(rel) == 0 {
		return nil
	}
	args := callArgs(c)
	if len(args) != len(callee.Params) {
		return nil
	}
	var out ctxMap
	for j := range rel {
		if f, ok := fa.factOf(args[j], caller, ctx, origin); ok {
			if out == nil {
				out = ctxMap{}
			}
			out[j] = f
		}
	}
	return out
}

func sameFact(a, b fact) bool {
	if a.kind != b.kind {
		return false
	}
	switch a.kind {
	case fkType:
		return types.Identical(a.typ, b.typ)
	case fkFunc:
		return a.fn == b.fn
	case fkConst:
		if a.isNil || b.isNil {
			return a.isNil && b.isNil
		}
		return a.val.Kind() == b.val.Kind() && constant.Compare(a.val, token.EQL, b.val)
	case fkLen:
		return a.n == b.n
	}
	return false
}

// intersect keeps only the facts both contexts agree on (a join: less information, more paths).
func intersect(a, b ctxMap) ctxMap {
	var out ctxMap
	for k, fa := range a {
		if fb, ok := b[k]; ok && sameFact(fa, fb) {
			if out == nil {
				out = ctxMap{}
			}
			if fb.origin > fa.origin {
				fa.origin = fb.origin
			}
			out[k] = fa
		}
	}
	return out
}

// ---------------------------------------------------------------------------------------------
// Condition evaluation (F2, F3).

const (
	srcParam uint8 = 1 << iota // a constant argument from the context
	srcField                   // a field that is never assigned
)

type ev struct {
	known  bool
	isNil  bool // the nil value
	nonNil bool // some non-nil value (an interface holding a type, a function)
	val    constant.Value
	srcs   uint8
	origin int
	desc   string
	field  string // F3: the field that is never assigned
}

func constDesc(f fact) string {
	if f.isNil {
		return "nil"
	}
	return f.val.ExactString()
}

func (fa *feas) eval(v ssa.Value, fn *ssa.Function, ctx ctxMap, depth int) ev {
	if depth > 8 {
		return ev{}
	}
	v = strip(v)
	if i := fa.paramOf(v, fn); i >= 0 {
		name := fn.Params[i].Name()
		f, ok := ctx[i]
		if !ok {
			return ev{desc: name}
		}
		switch f.kind {
		case fkConst:
			return ev{known: true, isNil: f.isNil, val: f.val, srcs: srcParam, origin: f.origin, desc: name}
		case fkType, fkFunc:
			return ev{known: true, nonNil: true, srcs: srcParam, origin: f.origin, desc: name}
		}
		return ev{desc: name}
	}
	switch x := v.(type) {
	case *ssa.Const:
		if x.Value != nil {
			return ev{known: true, val: x.Value, origin: -1, desc: x.Value.ExactString()}
		}
		if nilable(x.Type()) {
			return ev{known: true, isNil: true, origin: -1, desc: "nil"}
		}
		if z, ok := zeroConst(x.Type()); ok {
			return ev{known: true, val: z, origin: -1, desc: z.ExactString()}
		}
	case *ssa.UnOp:
		switch x.Op {
		case token.NOT:
			r := fa.eval(x.X, fn, ctx, depth+1)
			r.desc = "!" + r.desc
			if r.known && r.val != nil && r.val.Kind() == constant.Bool {
				r.val = constant.MakeBool(!constant.BoolVal(r.val))
				return r
			}
			r.known = false
			return r
		case token.MUL:
			if f, ok := x.X.(*ssa.FieldAddr); ok {
				return fa.fieldEval(f.X.Type(), f.Field)
			}
		}
	case *ssa.Field:
		return fa.fieldEval(x.X.Type(), x.Field)
	case *ssa.Call:
		if arg, ok := isLenCall(x); ok {
			return fa.evalLen(arg, fn, ctx)
		}
	case *ssa.BinOp:
		switch x.Op {
		case token.EQL, token.NEQ, token.LSS, token.LEQ, token.GTR, token.GEQ:
			a, b := fa.eval(x.X, fn, ctx, depth+1), fa.eval(x.Y, fn, ctx, depth+1)
			r := ev{srcs: a.srcs | b.srcs, origin: maxInt(a.origin, b.origin), desc: a.desc + " " + x.Op.String() + " " + b.desc}
			r.field = a.field + b.field
			if res, ok := compare(x.Op, a, b); ok {
				r.known, r.val = true, constant.MakeBool(res)
			}
			return r
		}
	}
	return ev{desc: shortValue(v)}
}

func shortValue(v ssa.Value) string {
	if v.Name() != "" {
		return v.Name()
	}
	return "?"
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func compare(op token.Token, a, b ev) (res bool, ok bool) {
	if !a.known || !b.known {
		return false, false
	}
	switch {
	case a.isNil || b.isNil:
		var eq bool
		switch {
		case a.isNil && b.isNil:
			eq = true
		case (a.isNil && b.nonNil) || (b.isNil && a.nonNil):
			eq = false
		default:
			return false, false
		}
		switch op {
		case token.EQL:
			return eq, true
		case token.NEQ:
			return !eq, true
		}
		return false, false
	case a.val == nil || b.val == nil:
		return false, false
	}
	ka, kb := a.val.Kind(), b.val.Kind()
	numeric := func(k constant.Kind) bool { return k == constant.Int || k == constant.Float }
	if !(ka == kb || (numeric(ka) && numeric(kb))) || ka == constant.Unknown || kb == constant.Unknown {
		return false, false
	}
	if (ka == constant.Bool || kb == constant.Bool) && op != token.EQL && op != token.NEQ {
		return false, false
	}
	defer func() {
		if recover() != nil {
			res, ok = false, false
		}
	}()
	return constant.Compare(a.val, op, b.val), true
}

func (fa *feas) evalLen(arg ssa.Value, fn *ssa.Function, ctx ctxMap) ev {
	arg = strip(arg)
	desc := "len(" + shortValue(arg) + ")"
	if i := fa.paramOf(arg, fn); i >= 0 {
		desc = "len(" + fn.Params[i].Name() + ")"
		f, ok := ctx[i]
		if !ok {
			return ev{desc: desc}
		}
		switch {
		case f.kind == fkLen:
			return ev{known: true, val: constant.MakeInt64(f.n), srcs: srcParam, origin: f.origin, desc: desc}
		case f.kind == fkConst && f.isNil:
			return ev{known: true, val: constant.MakeInt64(0), srcs: srcParam, origin: f.origin, desc: desc}
		case f.kind == fkConst && f.val != nil && f.val.Kind() == constant.String:
			return ev{known: true, val: constant.MakeInt64(int64(len(constant.StringVal(f.val)))), srcs: srcParam,
				origin: f.origin, desc: desc}
		}
		return ev{desc: desc}
	}
	if c, ok := arg.(*ssa.Const); ok {
		if c.Value == nil && nilable(c.Type()) {
			return ev{known: true, val: constant.MakeInt64(0), origin: -1, desc: desc}
		}
		if c.Value != nil && c.Value.Kind() == constant.String {
			return ev{known: true, val: constant.MakeInt64(int64(len(constant.StringVal(c.Value)))), origin: -1, desc: desc}
		}
	}
	return ev{desc: desc}
}

// fieldEval: a field that no code in the program assigns always holds its zero value (F3).
func (fa *feas) fieldEval(base types.Type, index int) ev {
	st, owner := structOf(base)
	if st == nil || index >= st.NumFields() {
		return ev{}
	}
	fv := st.Field(index)
	name := fv.Name()
	if owner != nil {
		name = types.TypeString(owner, nil) + "." + fv.Name()
	}
	desc := name
	if !fa.fieldIndex().neverSet(fv, owner) {
		return ev{desc: desc}
	}
	t := fv.Type()
	if nilable(t) {
		return ev{known: true, isNil: true, srcs: srcField, origin: -1, desc: desc, field: name}
	}
	if z, ok := zeroConst(t); ok {
		return ev{known: true, val: z, srcs: srcField, origin: -1, desc: desc, field: name}
	}
	return ev{desc: desc}
}

// structOf returns the struct type of base (or of *base) and the named type that declares it, if any.
func structOf(base types.Type) (*types.Struct, types.Type) {
	t := types.Unalias(base)
	if p, ok := t.Underlying().(*types.Pointer); ok {
		t = types.Unalias(p.Elem())
	}
	st, ok := t.Underlying().(*types.Struct)
	if !ok {
		return nil, nil
	}
	if _, named := t.(*types.Named); named {
		return st, t
	}
	return st, nil
}

// ---------------------------------------------------------------------------------------------
// Field assignments (F3). Built once, over every function of the program (reachable or not).

type fieldIndex struct {
	stored  map[*types.Var]bool // a Store to the field's address exists
	escaped map[*types.Var]bool // the field's address is used other than to load or store it
	ifaces  []types.Type        // every type converted to an interface (deduplicated)
	unsafes []types.Type        // every type an unsafe.Pointer is converted to
	convs   [][2]types.Type     // every ChangeType / Convert (from, to)
	exposed typeutil.Map        // cache: struct type -> bool
	nfuncs  int
}

func fieldKey(v *types.Var) *types.Var { return v.Origin() }

func (fa *feas) fieldIndex() *fieldIndex {
	if fa.fields != nil {
		return fa.fields
	}
	fi := &fieldIndex{stored: map[*types.Var]bool{}, escaped: map[*types.Var]bool{}}
	var seenIface typeutil.Map
	fieldOf := func(addr *ssa.FieldAddr) *types.Var {
		st, _ := structOf(addr.X.Type())
		if st == nil || addr.Field >= st.NumFields() {
			return nil
		}
		return fieldKey(st.Field(addr.Field))
	}
	for fn := range ssautil.AllFunctions(fa.prog) {
		fi.nfuncs++
		for _, b := range fn.Blocks {
			for _, ins := range b.Instrs {
				switch x := ins.(type) {
				case *ssa.FieldAddr:
					fv := fieldOf(x)
					if fv == nil {
						continue
					}
					for _, r := range *x.Referrers() {
						switch u := r.(type) {
						case *ssa.Store:
							if u.Addr == x && u.Val != ssa.Value(x) {
								fi.stored[fv] = true
							} else {
								fi.escaped[fv] = true
							}
						case *ssa.UnOp:
							if u.Op != token.MUL {
								fi.escaped[fv] = true
							}
						case *ssa.FieldAddr, *ssa.IndexAddr, *ssa.DebugRef:
							// a sub-address of the field: assignments to it do not set the field itself
							// to a non-zero value of a nilable or basic type (both have no sub-fields).
						default:
							fi.escaped[fv] = true
						}
					}
				case *ssa.MakeInterface:
					t := x.X.Type()
					if hasTypeParam(t) {
						continue // a generic body; its instances are scanned with concrete types
					}
					if seenIface.At(t) == nil {
						seenIface.Set(t, true)
						fi.ifaces = append(fi.ifaces, t)
					}
				case *ssa.Convert:
					if hasTypeParam(x.Type()) || hasTypeParam(x.X.Type()) {
						continue
					}
					if b, ok := x.X.Type().Underlying().(*types.Basic); ok && b.Kind() == types.UnsafePointer {
						fi.unsafes = append(fi.unsafes, x.Type())
					}
					fi.convs = append(fi.convs, [2]types.Type{x.X.Type(), x.Type()})
				case *ssa.ChangeType:
					if hasTypeParam(x.Type()) || hasTypeParam(x.X.Type()) {
						continue
					}
					fi.convs = append(fi.convs, [2]types.Type{x.X.Type(), x.Type()})
				}
			}
		}
	}
	fa.fields = fi
	fa.stats.FieldIndexFunctions = fi.nfuncs
	return fi
}

// reacher answers whether a value of type t can hold or point to a value of type target. Type graphs
// are finite and only named types can be recursive, so a cycle is cut at a named type in progress;
// a "no" that depended on such a cut is not memoised (it could be wrong), a "yes" always is.
type reacher struct {
	target types.Type
	memo   map[*types.Named]bool
	busy   map[*types.Named]bool
}

func newReacher(target types.Type) *reacher {
	return &reacher{target: target, memo: map[*types.Named]bool{}, busy: map[*types.Named]bool{}}
}

func (r *reacher) reaches(t types.Type) bool {
	ok, _ := r.walk(t)
	return ok
}

// walk returns (reaches, depended on a cycle cut).
func (r *reacher) walk(t types.Type) (bool, bool) {
	if t == nil {
		return false, false
	}
	t = types.Unalias(t)
	if types.Identical(t, r.target) {
		return true, false
	}
	if n, ok := t.(*types.Named); ok {
		if v, ok := r.memo[n]; ok {
			return v, false
		}
		if r.busy[n] {
			return false, true
		}
		r.busy[n] = true
		v, cut := r.walkUnder(n.Underlying())
		delete(r.busy, n)
		if v || !cut {
			r.memo[n] = v
		}
		return v, cut && !v
	}
	return r.walkUnder(t.Underlying())
}

func (r *reacher) walkUnder(u types.Type) (bool, bool) {
	anyCut := false
	try := func(t types.Type) bool {
		v, cut := r.walk(t)
		anyCut = anyCut || cut
		return v
	}
	switch x := u.(type) {
	case *types.Pointer:
		return try(x.Elem()), anyCut
	case *types.Slice:
		return try(x.Elem()), anyCut
	case *types.Array:
		return try(x.Elem()), anyCut
	case *types.Chan:
		return try(x.Elem()), anyCut
	case *types.Map:
		return try(x.Key()) || try(x.Elem()), anyCut
	case *types.Struct:
		for i := 0; i < x.NumFields(); i++ {
			if try(x.Field(i).Type()) {
				return true, false
			}
		}
		return false, anyCut
	}
	return false, false // basic, interface, signature, type parameter: no stored value of target inside
}

// neverSet: no Store to the field exists, its address never escapes, and no route that bypasses
// field stores is visible: a pointer to the struct (or to anything holding it) converted to an
// interface (reflection could set the field), an unsafe.Pointer converted to such a pointer, or a
// conversion from another struct type with the same layout.
func (fi *fieldIndex) neverSet(fv *types.Var, owner types.Type) bool {
	k := fieldKey(fv)
	if fi.stored[k] || fi.escaped[k] {
		return false
	}
	if owner == nil {
		return false // anonymous struct types: identity is too loose to be sure
	}
	if v := fi.exposed.At(owner); v != nil {
		return !v.(bool)
	}
	r := newReacher(owner)
	exposed := false
	for _, t := range fi.ifaces {
		if types.Identical(types.Unalias(t), owner) {
			continue // a copy of the struct value in an interface is not addressable
		}
		if r.reaches(t) {
			exposed = true
			break
		}
	}
	for _, t := range fi.unsafes {
		if !exposed && r.reaches(t) {
			exposed = true
		}
	}
	for _, c := range fi.convs {
		if exposed {
			break
		}
		from, to := c[0], c[1]
		if types.Identical(from, to) {
			continue
		}
		if r.reaches(to) && !r.reaches(from) {
			exposed = true
		}
	}
	fi.exposed.Set(owner, exposed)
	return !exposed
}

// ---------------------------------------------------------------------------------------------
// One step.

type infeasible struct {
	pattern string
	origin  int // path edge index the deciding value came from; -1 if none
	reason  func(siteOf func(int) string) string
}

func recvType(fn *ssa.Function) types.Type {
	if r := fn.Signature.Recv(); r != nil {
		return r.Type()
	}
	return nil
}

func deref(t types.Type) types.Type {
	if p, ok := types.Unalias(t).Underlying().(*types.Pointer); ok {
		return p.Elem()
	}
	return t
}

// staticChain: fn itself plus the functions a synthetic forwarder calls statically (a few levels).
func staticChain(fn *ssa.Function) []*ssa.Function {
	out := []*ssa.Function{fn}
	cur := fn
	for d := 0; d < maxWrapperDepth && cur != nil && cur.Synthetic != ""; d++ {
		var next *ssa.Function
		for _, b := range cur.Blocks {
			for _, ins := range b.Instrs {
				if c, ok := ins.(ssa.CallInstruction); ok {
					if sc := c.Common().StaticCallee(); sc != nil {
						out = append(out, sc)
						if next == nil {
							next = sc
						}
					}
				}
			}
		}
		cur = next
	}
	return out
}

func sameFunc(a, b *ssa.Function) bool {
	if a == nil || b == nil {
		return true // unknown: conservative
	}
	if a == b || a.String() == b.String() {
		return true
	}
	if a.Origin() != nil && (a.Origin() == b || a.Origin() == b.Origin()) {
		return true
	}
	if b.Origin() != nil && b.Origin() == a {
		return true
	}
	return false
}

func calleeMatches(expected, callee *ssa.Function) bool {
	for _, f := range staticChain(expected) {
		if sameFunc(f, callee) {
			return true
		}
	}
	return false
}

func (fa *feas) lookupMethod(t types.Type, m *types.Func) (fn *ssa.Function) {
	defer func() {
		if recover() != nil {
			fn = nil
		}
	}()
	sel := fa.prog.MethodSets.MethodSet(t).Lookup(m.Pkg(), m.Name())
	if sel == nil {
		return nil
	}
	return fa.prog.MethodValue(sel)
}

func typeStr(t types.Type) string { return types.TypeString(t, nil) }

// checkInstr returns nil if the call instruction can run and reach the callee under ctx.
func (fa *feas) checkInstr(caller, callee *ssa.Function, c ssa.CallInstruction, ctx ctxMap) *infeasible {
	// F2 / F3: a branch that must be taken to reach the call site.
	for _, gd := range fa.guardsOf(c) {
		r := fa.eval(gd.cond, caller, ctx, 0)
		if !r.known || r.val == nil || r.val.Kind() != constant.Bool || constant.BoolVal(r.val) == gd.want {
			continue
		}
		want, desc := gd.want, r.desc
		switch {
		case r.srcs&srcField != 0:
			field := r.field
			return &infeasible{pattern: PatF3, origin: -1, reason: func(siteOf func(int) string) string {
				return fmt.Sprintf("the call at %s runs only if `%s` is %v; field %s is never assigned in the analysed program, so it is always its zero value",
					siteOf(-2), desc, want, field)
			}}
		case r.srcs&srcParam != 0:
			origin := r.origin
			return &infeasible{pattern: PatF2, origin: origin, reason: func(siteOf func(int) string) string {
				return fmt.Sprintf("the call at %s runs only if `%s` is %v; with the argument passed at %s it is %v",
					siteOf(-2), desc, want, siteOf(origin), !want)
			}}
		}
	}
	// F1: a dynamic call on a parameter whose value on this path is known.
	common := c.Common()
	if common.StaticCallee() != nil || callee == nil {
		return nil
	}
	i := fa.paramOf(strip(common.Value), caller)
	if i < 0 {
		return nil
	}
	f, ok := ctx[i]
	if !ok {
		return nil
	}
	if common.IsInvoke() {
		if f.kind != fkType || hasTypeParam(f.typ) {
			return nil
		}
		expected := fa.lookupMethod(f.typ, common.Method)
		if expected == nil || calleeMatches(expected, callee) {
			return nil
		}
		rt := recvType(callee)
		if rt == nil || hasTypeParam(rt) || types.Identical(deref(rt), deref(f.typ)) {
			return nil
		}
		dyn, recv, name, origin := typeStr(f.typ), typeStr(rt), funcName(callee), f.origin
		return &infeasible{pattern: PatF1, origin: origin, reason: func(siteOf func(int) string) string {
			return fmt.Sprintf("the argument passed at %s is `%s`; the dynamic call at %s can only reach its method, not %s (receiver `%s`)",
				siteOf(origin), dyn, siteOf(-2), name, recv)
		}}
	}
	if f.kind != fkFunc || calleeMatches(f.fn, callee) {
		return nil
	}
	val, name, origin := funcName(f.fn), funcName(callee), f.origin
	return &infeasible{pattern: PatF1, origin: origin, reason: func(siteOf func(int) string) string {
		return fmt.Sprintf("the function value passed at %s is `%s`; the dynamic call at %s can only reach it, not %s",
			siteOf(origin), val, siteOf(-2), name)
	}}
}

// step decides one edge under ctx: (child context, nil) when it can run, else (nil, reason).
// origin is the edge's index on the path (for fact origins), or -1.
func (fa *feas) step(from, ei int, ctx ctxMap, origin int) (ctxMap, *infeasible) {
	e := fa.g.out[from][ei]
	instrs := fa.instrOut[from][ei]
	caller, callee := fa.fnOf[from], fa.fnOf[e.To]
	if len(instrs) == 0 || caller == nil {
		return nil, nil // synthetic edge without an instruction: feasible, nothing known after it
	}
	var first *infeasible
	var child ctxMap
	okAny := false
	for _, c := range instrs {
		if inf := fa.checkInstr(caller, callee, c, ctx); inf != nil {
			if first == nil {
				first = inf
			}
			continue
		}
		cc := fa.childCtx(e.To, caller, c, ctx, origin)
		if !okAny {
			child, okAny = cc, true
		} else {
			child = intersect(child, cc)
		}
	}
	if !okAny {
		return nil, first
	}
	return child, nil
}

// checkPath runs the precise check along one path (no merging) and returns its first infeasible step.
func (fa *feas) checkPath(p foundPath) *InfeasibleStep {
	var ctx ctxMap
	for i, e := range p.Edges {
		ei := fa.edgeIndex(e)
		if ei < 0 {
			return nil // cannot map the edge: conservative
		}
		child, inf := fa.step(e.From, ei, ctx, i)
		if inf != nil {
			siteOf := func(k int) string {
				if k == -2 {
					k = i
				}
				if k < 0 || k >= len(p.Edges) {
					return "(unknown)"
				}
				s := p.Edges[k].Site
				if s.File == "" {
					return "(synthetic call)"
				}
				return fmt.Sprintf("%s:%d", s.File, s.Line)
			}
			st := &InfeasibleStep{Pattern: inf.pattern, EdgeIndex: i, Edge: fa.pathEdge(e),
				ContextEdges: []PathEdge{}, Reason: inf.reason(siteOf)}
			if inf.origin >= 0 && inf.origin < i {
				for _, ce := range p.Edges[inf.origin:i] {
					st.ContextEdges = append(st.ContextEdges, fa.pathEdge(ce))
				}
			}
			return st
		}
		ctx = child
	}
	return nil
}

func (fa *feas) pathEdge(e gEdge) PathEdge {
	return PathEdge{Caller: fa.g.nodes[e.From].Name(), Callee: fa.g.nodes[e.To].Name(), CallSite: e.Site, Kind: e.Kind}
}

func (fa *feas) edgeIndex(e gEdge) int {
	for i, x := range fa.g.out[e.From] {
		if x == e {
			return i
		}
	}
	return -1
}

// ---------------------------------------------------------------------------------------------
// State search.

func (fa *feas) ctxKey(c ctxMap) string {
	if len(c) == 0 {
		return ""
	}
	keys := make([]int, 0, len(c))
	for k := range c {
		keys = append(keys, k)
	}
	sort.Ints(keys)
	var b strings.Builder
	for _, k := range keys {
		f := c[k]
		fmt.Fprintf(&b, "%d:", k)
		switch f.kind {
		case fkType:
			fmt.Fprintf(&b, "T%d", fa.typeID(f.typ))
		case fkFunc:
			fmt.Fprintf(&b, "F%p", f.fn)
		case fkConst:
			if f.isNil {
				fmt.Fprintf(&b, "Cnil/%d", fa.typeID(f.ctyp))
			} else {
				fmt.Fprintf(&b, "C%s/%d", f.val.ExactString(), fa.typeID(f.ctyp))
			}
		case fkLen:
			fmt.Fprintf(&b, "L%d", f.n)
		}
		b.WriteByte(';')
	}
	return b.String()
}

func (fa *feas) typeID(t types.Type) int {
	if v := fa.types.At(t); v != nil {
		return v.(int)
	}
	fa.ntypes++
	fa.types.Set(t, fa.ntypes)
	return fa.ntypes
}

func (fa *feas) internCtx(c ctxMap) int32 {
	k := fa.ctxKey(c)
	if id, ok := fa.ctxIndex[k]; ok {
		return id
	}
	id := int32(len(fa.ctxs))
	fa.ctxs = append(fa.ctxs, c)
	fa.ctxIndex[k] = id
	return id
}

func stateKey(node, ctx int32, approx bool) uint64 {
	k := uint64(node)<<33 | uint64(ctx)<<1
	if approx {
		k |= 1
	}
	return k
}

// search explores every state reachable from the roots (breadth first, so the first state found at
// a node lies on a shortest feasible path). Contexts per node beyond the cap are merged into the
// empty context and marked approximate; anything reached only through them is UNDECIDED.
func (fa *feas) search() {
	start := time.Now()
	fa.ctxs, fa.ctxIndex = []ctxMap{nil}, map[string]int32{"": 0}
	fa.seen, fa.firstAt, fa.approxAt = map[uint64]int32{}, map[int]int32{}, map[int]int32{}
	nctx := map[int32]int{}
	over := map[int32]bool{}
	add := func(node, ctx int32, approx bool, pred, edge int32) {
		if !approx && ctx != 0 {
			if _, done := fa.seen[stateKey(node, 0, false)]; done {
				return // the empty context at this node already allows everything this one allows
			}
			if _, done := fa.seen[stateKey(node, ctx, false)]; !done && nctx[node] >= fa.lim.MaxContextsPerNode {
				over[node] = true
				ctx, approx = 0, true
			}
		}
		k := stateKey(node, ctx, approx)
		if _, done := fa.seen[k]; done {
			return
		}
		if approx {
			if _, done := fa.seen[stateKey(node, 0, false)]; done {
				return
			}
		}
		if len(fa.states) >= fa.lim.MaxStates {
			fa.aborted = true
			return
		}
		id := int32(len(fa.states))
		fa.states = append(fa.states, stRec{node: node, ctx: ctx, approx: approx, pred: pred, edge: edge})
		fa.seen[k] = id
		if !approx {
			if ctx != 0 {
				nctx[node]++
			}
			if _, ok := fa.firstAt[int(node)]; !ok {
				fa.firstAt[int(node)] = id
			}
		} else if _, ok := fa.approxAt[int(node)]; !ok {
			fa.approxAt[int(node)] = id
		}
	}
	for _, r := range fa.roots {
		add(int32(r), 0, false, -1, -1)
	}
	for i := 0; i < len(fa.states) && !fa.aborted; i++ {
		s := fa.states[i]
		ctx := fa.ctxs[s.ctx]
		for ei, e := range fa.g.out[s.node] {
			child, inf := fa.step(int(s.node), ei, ctx, -1)
			if inf != nil {
				continue
			}
			add(int32(e.To), fa.internCtx(child), s.approx, int32(i), int32(ei))
			if fa.aborted {
				break
			}
		}
	}
	for _, s := range fa.states {
		if s.approx {
			fa.stats.ApproximateStates++
		}
	}
	fa.stats.States = len(fa.states)
	fa.stats.NodesOverContextCap = len(over)
	fa.stats.StateLimitHit = fa.aborted
	fa.stats.DurationMS += time.Since(start).Milliseconds()
}

func (fa *feas) statePath(id int32) foundPath {
	var rev []gEdge
	for cur := id; ; {
		s := fa.states[cur]
		if s.pred < 0 {
			p := foundPath{Root: int(s.node)}
			for i := len(rev) - 1; i >= 0; i-- {
				p.Edges = append(p.Edges, rev[i])
			}
			return p
		}
		ps := fa.states[s.pred]
		rev = append(rev, fa.g.out[ps.node][s.edge])
		cur = s.pred
	}
}

// ---------------------------------------------------------------------------------------------
// N shortest distinct simple paths (A* backwards from the targets with the exact distance from
// the roots as heuristic, so complete paths come out in non-decreasing length).

type sufNode struct {
	e    gEdge
	next *sufNode
}

type pitem struct {
	f, seq, length, head int
	suf                  *sufNode
}

type pqueue []pitem

func (q pqueue) Len() int { return len(q) }
func (q pqueue) Less(i, j int) bool {
	if q[i].f != q[j].f {
		return q[i].f < q[j].f
	}
	return q[i].seq < q[j].seq
}
func (q pqueue) Swap(i, j int) { q[i], q[j] = q[j], q[i] }
func (q *pqueue) Push(x any)   { *q = append(*q, x.(pitem)) }
func (q *pqueue) Pop() any {
	old := *q
	it := old[len(old)-1]
	*q = old[:len(old)-1]
	return it
}

func (fa *feas) distFromRoots() []int {
	dist := make([]int, len(fa.g.nodes))
	for i := range dist {
		dist[i] = -1
	}
	var queue []int
	for _, r := range fa.roots {
		if dist[r] < 0 {
			dist[r] = 0
			queue = append(queue, r)
		}
	}
	for len(queue) > 0 {
		n := queue[0]
		queue = queue[1:]
		for _, e := range fa.g.out[n] {
			if dist[e.To] < 0 {
				dist[e.To] = dist[n] + 1
				queue = append(queue, e.To)
			}
		}
	}
	return dist
}

func (fa *feas) shortestN(targets []int, dist []int, n int) ([]foundPath, bool) {
	isRoot := map[int]bool{}
	for _, r := range fa.roots {
		isRoot[r] = true
	}
	q := &pqueue{}
	seq := 0
	for _, t := range targets {
		if dist[t] >= 0 {
			heap.Push(q, pitem{f: dist[t], seq: seq, head: t})
			seq++
		}
	}
	var out []foundPath
	for pops := 0; q.Len() > 0 && len(out) < n; pops++ {
		if pops >= maxEnumPops {
			return out, true
		}
		it := heap.Pop(q).(pitem)
		if isRoot[it.head] {
			p := foundPath{Root: it.head}
			for s := it.suf; s != nil; s = s.next {
				p.Edges = append(p.Edges, s.e)
			}
			out = append(out, p)
			continue
		}
		for _, r := range fa.in[it.head] {
			e := fa.g.out[r.from][r.idx]
			u := e.From
			if dist[u] < 0 || u == it.head {
				continue
			}
			onPath := false
			for s := it.suf; s != nil; s = s.next {
				if s.e.To == u {
					onPath = true
					break
				}
			}
			if onPath {
				continue
			}
			heap.Push(q, pitem{f: it.length + 1 + dist[u], seq: seq, length: it.length + 1, head: u,
				suf: &sufNode{e: e, next: it.suf}})
			seq++
		}
	}
	return out, false
}

// ---------------------------------------------------------------------------------------------

func strp(s string) *string { return &s }

// forTarget decides one PATH_FOUND target (graph nodes targetIDs).
func (fa *feas) forTarget(t Target, targetIDs []int, dist []int) *FeasibilityResult {
	start := time.Now()
	defer func() { fa.stats.DurationMS += time.Since(start).Milliseconds() }()
	res := &FeasibilityResult{MaxExaminedPaths: fa.lim.MaxExaminedPaths, Examined: []ExaminedPath{}}
	ids := append([]int(nil), targetIDs...)
	sort.Ints(ids)
	paths, truncated := fa.shortestN(ids, dist, fa.lim.MaxExaminedPaths)
	res.ExaminedTruncated = truncated
	var evidence *foundPath
	for i := range paths {
		step := fa.checkPath(paths[i])
		res.Examined = append(res.Examined, ExaminedPath{Length: len(paths[i].Edges), FirstInfeasible: step})
		if step == nil && evidence == nil {
			evidence = &paths[i]
			res.EvidenceSource = strp(EvidenceExamined)
		}
	}
	best, approx := int32(-1), int32(-1)
	for _, id := range ids {
		if s, ok := fa.firstAt[id]; ok && (best < 0 || s < best) {
			best = s
		}
		if s, ok := fa.approxAt[id]; ok && (approx < 0 || s < approx) {
			approx = s
		}
	}
	switch {
	case evidence != nil:
		res.Status = FeasFeasible
	case best >= 0:
		p := fa.statePath(best)
		if fa.checkPath(p) != nil {
			res.Status, res.UndecidedReason = FeasUndecided, strp(UndecidedInconsistent)
			break
		}
		evidence, res.Status, res.EvidenceSource = &p, FeasFeasible, strp(EvidenceSearch)
	case fa.aborted:
		res.Status, res.UndecidedReason = FeasUndecided, strp(UndecidedStateLimit)
	case approx >= 0:
		res.Status, res.UndecidedReason = FeasUndecided, strp(UndecidedContextLimit)
	default:
		res.Status = FeasInfeasible
		for _, ex := range res.Examined {
			if ex.FirstInfeasible == nil {
				res.Status, res.UndecidedReason = FeasUndecided, strp(UndecidedInconsistent)
			}
		}
	}
	if evidence != nil {
		cp := toCallPath(fa.g, t, *evidence)
		res.EvidencePath = &cp
	}
	if res.Status != FeasFeasible {
		res.EvidenceSource = nil
	}
	return res
}

// applyFeasibility fills the feasibility field of every PATH_FOUND result.
func applyFeasibility(a *analysis, req *Request, results []TargetResult, targetIDs [][]int) *FeasibilityStats {
	fa := newFeas(a, req.Feasibility)
	fa.search()
	dist := fa.distFromRoots()
	for i := range results {
		if results[i].Result != ResultPathFound || len(targetIDs[i]) == 0 {
			continue
		}
		results[i].Feasibility = fa.forTarget(results[i].Target, targetIDs[i], dist)
	}
	st := fa.stats
	return &st
}
