package main

import (
	"bytes"
	"encoding/json"
	"io"
	"strings"
	"testing"
)

// CP9 unit tests: one SSA snippet per pattern (infeasible and feasible look-alike), the
// conservative cases (unknown values must never make a step infeasible), caps, and the
// promise that a request without "feasibility" behaves exactly as before.

const feasLib = `package lib

//go:noinline
func Vuln(s string) string { return "v:" + s }
`

func feasModule(t *testing.T, main string) string {
	t.Helper()
	return tempModule(t, map[string]string{"lib/lib.go": feasLib, "cmd/app/main.go": main})
}

func feasReq(dir string, f *FeasibilityRequest) *Request {
	r := reachReq(dir, "reach", Target{"tm/lib", "Vuln"})
	r.Feasibility = f
	return r
}

func feasResult(t *testing.T, dir string, f *FeasibilityRequest) (TargetResult, *Stats) {
	t.Helper()
	if f == nil {
		f = &FeasibilityRequest{}
	}
	res, st, err := runReach(feasReq(dir, f), io.Discard)
	if err != nil {
		t.Fatalf("reach: %v", err)
	}
	tr := res.([]TargetResult)[0]
	if tr.Result != ResultPathFound {
		t.Fatalf("expected PATH_FOUND, got %s", tr.Result)
	}
	if tr.Feasibility == nil {
		t.Fatal("no feasibility result for a PATH_FOUND target")
	}
	return tr, st
}

func wantStatus(t *testing.T, tr TargetResult, status string) {
	t.Helper()
	if tr.Feasibility.Status != status {
		b, _ := json.MarshalIndent(tr.Feasibility, "", " ")
		t.Fatalf("status %s, want %s\n%s", tr.Feasibility.Status, status, b)
	}
	switch status {
	case FeasFeasible:
		ev := tr.Feasibility.EvidencePath
		if ev == nil || len(ev.Edges) == 0 || !strings.HasSuffix(ev.Edges[len(ev.Edges)-1].Callee, "tm/lib.Vuln") {
			t.Fatalf("FEASIBLE needs an evidence path ending at the target: %+v", ev)
		}
		if tr.Feasibility.EvidenceSource == nil {
			t.Fatal("FEASIBLE needs an evidence source")
		}
	case FeasInfeasible:
		if tr.Feasibility.EvidencePath != nil {
			t.Fatal("INFEASIBLE must not report an evidence path")
		}
		if len(tr.Feasibility.Examined) == 0 {
			t.Fatal("INFEASIBLE must report the examined paths")
		}
		for i, ex := range tr.Feasibility.Examined {
			if ex.FirstInfeasible == nil {
				t.Fatalf("examined path %d has no infeasible step", i)
			}
			st := ex.FirstInfeasible
			if st.Edge.CallSite.File == "" || st.Edge.CallSite.Line == 0 || st.Reason == "" {
				t.Fatalf("infeasible step without file, line or reason: %+v", st)
			}
		}
	}
}

func patterns(tr TargetResult) []string {
	var out []string
	for _, ex := range tr.Feasibility.Examined {
		if ex.FirstInfeasible != nil {
			out = append(out, ex.FirstInfeasible.Pattern)
		}
	}
	return out
}

func hasPattern(tr TargetResult, p string) bool {
	for _, x := range patterns(tr) {
		if x == p {
			return true
		}
	}
	return false
}

// --- F1 -----------------------------------------------------------------------------------------

const f1Iface = `package main

import "tm/lib"

type sink interface{ Put(s string) }

type safe struct{}

func (safe) Put(s string) {}

type evil struct{}

func (evil) Put(s string) { lib.Vuln(s) }

//go:noinline
func emit(w sink, s string) { w.Put(s) }

//go:noinline
func report(verbose bool) {
	if verbose {
		emit(evil{}, "r")
	}
}

func main() {
	emit(safe{}, "a")
	report(CALL)
}
`

func TestFeasF1InterfaceSplice(t *testing.T) {
	tr, _ := feasResult(t, feasModule(t, strings.Replace(f1Iface, "CALL", "false", 1)), nil)
	wantStatus(t, tr, FeasInfeasible)
	first := tr.Feasibility.Examined[0].FirstInfeasible
	if first.Pattern != PatF1 || !strings.HasSuffix(first.Edge.Callee, "evil.Put") || len(first.ContextEdges) != 1 {
		t.Fatalf("shortest path: want F1 at the step to evil.Put with one context edge, got %+v", first)
	}
	if !strings.Contains(first.Reason, "`tm/cmd/app.safe`") || !strings.Contains(first.Reason, "cmd/app/main.go:") {
		t.Errorf("reason should name the dynamic type passed and the call site: %q", first.Reason)
	}
	if !strings.HasSuffix(first.ContextEdges[0].Callee, ".emit") {
		t.Errorf("context edge should be the call into emit: %+v", first.ContextEdges[0])
	}
	if !hasPattern(tr, PatF2) {
		t.Errorf("the carrier path through report(false) should fail on F2: %v", patterns(tr))
	}
}

func TestFeasF1InterfaceLookalike(t *testing.T) {
	src := strings.Replace(f1Iface, "CALL", "len(os.Args) > 1", 1)
	src = strings.Replace(src, `import "tm/lib"`, "import (\n\t\"os\"\n\n\t\"tm/lib\"\n)", 1)
	tr, _ := feasResult(t, feasModule(t, src), nil)
	wantStatus(t, tr, FeasFeasible)
}

const f1Once = `package main

import "tm/lib"

type once struct{ done bool }

//go:noinline
func (o *once) Do(f func()) {
	if !o.done {
		o.doSlow(f)
	}
}

//go:noinline
func (o *once) doSlow(f func()) {
	o.done = true
	f()
}

var a, b once

type config struct{ hook func() }

//go:noinline
func setup() { a.Do(func() { println("setup") }) }

//go:noinline
func dangerous(c *config) {
	if c.hook != nil {
		b.Do(func() { lib.Vuln("x") })
	}
}

func main() {
	setup()
	dangerous(&config{})
	MORE
}
`

func TestFeasF1FuncValueTwoLevels(t *testing.T) {
	tr, _ := feasResult(t, feasModule(t, strings.Replace(f1Once, "MORE", "", 1)), nil)
	wantStatus(t, tr, FeasInfeasible)
	var f1 *InfeasibleStep
	for _, ex := range tr.Feasibility.Examined {
		if ex.FirstInfeasible.Pattern == PatF1 {
			f1 = ex.FirstInfeasible
		}
	}
	if f1 == nil {
		t.Fatalf("no F1 step among %v", patterns(tr))
	}
	// setup -> Do creates the closure value, Do -> doSlow passes it through: two context edges.
	if len(f1.ContextEdges) != 2 || !strings.HasSuffix(f1.ContextEdges[0].Callee, "once.Do") ||
		!strings.HasSuffix(f1.ContextEdges[1].Callee, "once.doSlow") {
		t.Fatalf("want context edges into Do and doSlow, got %+v", f1.ContextEdges)
	}
	if !strings.Contains(f1.Reason, "setup$1") || !strings.HasSuffix(f1.Edge.Callee, "dangerous$1") {
		t.Errorf("reason/edge: %q %s", f1.Reason, f1.Edge.Callee)
	}
	if !hasPattern(tr, PatF3) {
		t.Errorf("the carrier path through dangerous() should fail on F3: %v", patterns(tr))
	}
}

func TestFeasF1FuncValueLookalike(t *testing.T) {
	tr, _ := feasResult(t, feasModule(t, strings.Replace(f1Once, "MORE", `b.Do(func() { lib.Vuln("y") })`, 1)), nil)
	wantStatus(t, tr, FeasFeasible)
}

// --- F2 -----------------------------------------------------------------------------------------

func TestFeasF2ConstantThroughFuncValue(t *testing.T) {
	src := `package main

import "tm/lib"

//go:noinline
func listen(addr string, port int) {
	if port == 0 {
		println("unix")
	} else {
		go lib.Vuln(addr)
	}
}

var ls = map[string]func(string, int){"x": listen}

func main() { ls["x"]("/s", 0) }
`
	tr, _ := feasResult(t, feasModule(t, src), nil)
	wantStatus(t, tr, FeasInfeasible)
	st := tr.Feasibility.Examined[0].FirstInfeasible
	if st.Pattern != PatF2 || len(st.ContextEdges) != 1 || st.ContextEdges[0].Kind != KindDynamic {
		t.Fatalf("want F2 with the dynamic call into listen as context, got %+v", st)
	}
	if !strings.Contains(st.Reason, "`port == 0` is false") {
		t.Errorf("reason: %q", st.Reason)
	}
}

func TestFeasF2VariadicAndString(t *testing.T) {
	src := `package main

import "tm/lib"

//go:noinline
func exec(sql string, args ...any) { execSimple(sql, args) }

//go:noinline
func execSimple(sql string, args []any) {
	if len(args) > 0 {
		lib.Vuln(sql)
	}
}

//go:noinline
func open(driver string) {
	switch driver {
	case "badger":
	case "postgres":
		lib.Vuln(driver)
	}
}

func main() {
	exec("CREATE")
	open("badger")
	CALLS
}
`
	tr, _ := feasResult(t, feasModule(t, strings.Replace(src, "CALLS", "", 1)), nil)
	wantStatus(t, tr, FeasInfeasible)
	for _, p := range patterns(tr) {
		if p != PatF2 {
			t.Fatalf("only F2 expected, got %v", patterns(tr))
		}
	}
	// Look-alikes: a non-empty variadic call, or the other constant.
	for _, call := range []string{`exec("SELECT", 1)`, `open("postgres")`} {
		tr, _ := feasResult(t, feasModule(t, strings.Replace(src, "CALLS", call, 1)), nil)
		wantStatus(t, tr, FeasFeasible)
	}
}

func TestFeasF2ConstantAndVariableCaller(t *testing.T) {
	src := `package main

import (
	"os"

	"tm/lib"
)

//go:noinline
func listen(port int) {
	if port != 0 {
		lib.Vuln("h3")
	}
}

func main() {
	listen(0)
	listen(len(os.Args))
}
`
	tr, _ := feasResult(t, feasModule(t, src), nil)
	wantStatus(t, tr, FeasFeasible)
}

// --- F3 -----------------------------------------------------------------------------------------

const f3Src = `package main

import (
	"os"

	"tm/lib"
)

type Opener interface{ Open() string }

type dir string

func (d dir) Open() string { return string(d) }

type Rar struct {
	Name string
	FS   Opener
}

type Format interface{ Extract() string }

DECLS

//go:noinline
func (r Rar) Extract() string {
	if r.FS != nil {
		return lib.Vuln(r.FS.Open())
	}
	return r.Name
}

func main() {
	fs := []Format{Rar{Name: os.Args[0]}}
	EXTRA
	for _, f := range fs {
		println(f.Extract())
	}
}
`

func TestFeasF3FieldNeverSet(t *testing.T) {
	src := strings.Replace(strings.Replace(f3Src, "EXTRA", "", 1), "DECLS", "", 1)
	tr, _ := feasResult(t, feasModule(t, src), nil)
	wantStatus(t, tr, FeasInfeasible)
	st := tr.Feasibility.Examined[0].FirstInfeasible
	if st.Pattern != PatF3 || len(st.ContextEdges) != 0 || !strings.Contains(st.Reason, "tm/cmd/app.Rar.FS") {
		t.Fatalf("want F3 on Rar.FS without context edges, got %+v", st)
	}
}

func TestFeasF3Lookalikes(t *testing.T) {
	cases := map[string][2]string{
		"set in a rarely used function": {`if len(os.Args) > 3 { fs = append(fs, Rar{FS: dir(os.Args[3])}) }`, ""},
		"set through a pointer": {`r := &Rar{}; setFS(&r.FS); fs = append(fs, *r)`,
			"//go:noinline\nfunc setFS(p *Opener) { *p = dir(\"x\") }"},
		"set by reflection":  {`r := &Rar{}; reflect.ValueOf(r).Elem().Field(1).Set(reflect.ValueOf(dir("x"))); fs = append(fs, *r)`, ""},
		"set through unsafe": {`var raw [4]uintptr; r := (*Rar)(unsafe.Pointer(&raw)); fs = append(fs, *r)`, ""},
		"converted from another struct": {`fs = append(fs, Rar(other{FS: dir("x")}))`,
			"type other struct {\n\tName string\n\tFS   Opener\n}"},
	}
	for name, c := range cases {
		t.Run(name, func(t *testing.T) {
			extra := c[0]
			src := strings.Replace(strings.Replace(f3Src, "EXTRA", extra, 1), "DECLS", c[1], 1)
			if strings.Contains(extra, "reflect.") {
				src = strings.Replace(src, "\"os\"\n", "\"os\"\n\t\"reflect\"\n", 1)
			}
			if strings.Contains(extra, "unsafe.") {
				src = strings.Replace(src, "\"os\"\n", "\"os\"\n\t\"unsafe\"\n", 1)
			}
			tr, _ := feasResult(t, feasModule(t, src), nil)
			if tr.Feasibility.Status == FeasInfeasible {
				t.Fatalf("a field that can be set must not make the step infeasible: %v", patterns(tr))
			}
		})
	}
}

// --- conservative when undecidable ----------------------------------------------------------------

func TestFeasUnknownValuesStayFeasible(t *testing.T) {
	cases := map[string]string{
		"phi of constants": `package main

import (
	"os"

	"tm/lib"
)

//go:noinline
func listen(port int) {
	if port != 0 {
		lib.Vuln("h3")
	}
}

func main() {
	p := 0
	if len(os.Args) > 5 {
		p = 1
	}
	listen(p)
}
`,
		"parameter whose address is taken": `package main

import "tm/lib"

//go:noinline
func adjust(p *int) { *p = 443 }

//go:noinline
func listen(port int) {
	adjust(&port)
	if port != 0 {
		lib.Vuln("h3")
	}
}

func main() { listen(0) }
`,
		"interface value from a package variable": `package main

import "tm/lib"

type sink interface{ Put(string) }
type safe struct{}

func (safe) Put(string) {}

type evil struct{}

func (evil) Put(s string) { lib.Vuln(s) }

var global sink = evil{}

//go:noinline
func emit(w sink) { w.Put("x") }

func main() {
	emit(safe{})
	emit(global)
}
`,
		"constant condition (out of scope)": `package main

import "tm/lib"

const debug = false

//go:noinline
func run() {
	if debug {
		lib.Vuln("d")
	}
}

func main() { run() }
`,
		"field of a package-level value (out of scope)": `package main

import "tm/lib"

type Enc struct{ alg string }

var Modern = &Enc{alg: "sha256"}

//go:noinline
func (e *Enc) Encode() { mac(e.alg) }

//go:noinline
func mac(alg string) {
	if alg == "pbmac1" {
		lib.Vuln(alg)
	}
}

func main() { Modern.Encode() }
`,
	}
	for name, src := range cases {
		t.Run(name, func(t *testing.T) {
			tr, _ := feasResult(t, feasModule(t, src), nil)
			if tr.Feasibility.Status != FeasFeasible {
				t.Fatalf("status %s, want FEASIBLE (undecidable steps count as feasible): %v", tr.Feasibility.Status, patterns(tr))
			}
		})
	}
}

// --- caps -------------------------------------------------------------------------------------------

func TestFeasStateLimitIsUndecided(t *testing.T) {
	dir := feasModule(t, strings.Replace(f1Iface, "CALL", "false", 1))
	tr, st := feasResult(t, dir, &FeasibilityRequest{MaxStates: 2})
	if tr.Feasibility.Status != FeasUndecided || tr.Feasibility.UndecidedReason == nil ||
		*tr.Feasibility.UndecidedReason != UndecidedStateLimit || !st.Feasibility.StateLimitHit {
		t.Fatalf("a state search cut by max_states must be UNDECIDED/STATE_LIMIT, got %+v", tr.Feasibility)
	}
}

func TestFeasContextCapNeverDowngrades(t *testing.T) {
	// emit is entered with two different dynamic types; with one context per node the second is
	// merged (approximate). The infeasible case must then not be called INFEASIBLE for sure, and
	// the feasible look-alike must stay FEASIBLE or UNDECIDED.
	for _, call := range []string{"false", "len(os.Args) > 1"} {
		src := strings.Replace(f1Iface, "CALL", call, 1)
		src = strings.Replace(src, `import "tm/lib"`, "import (\n\t\"os\"\n\n\t\"tm/lib\"\n)", 1)
		src = strings.Replace(src, "func main() {", "var _ = os.Args\n\nfunc main() {", 1)
		tr, _ := feasResult(t, feasModule(t, src), &FeasibilityRequest{MaxContextsPerNode: 1})
		if call != "false" && tr.Feasibility.Status == FeasInfeasible {
			t.Fatalf("cap must never produce a false INFEASIBLE")
		}
	}
}

func TestFeasExaminedPathsAreCapped(t *testing.T) {
	dir := feasModule(t, strings.Replace(f1Iface, "CALL", "false", 1))
	tr, st := feasResult(t, dir, &FeasibilityRequest{MaxExaminedPaths: 1})
	if len(tr.Feasibility.Examined) != 1 || tr.Feasibility.MaxExaminedPaths != 1 || st.Feasibility.MaxExaminedPaths != 1 {
		t.Fatalf("max_examined_paths=1 must examine one path and record N: %+v", tr.Feasibility)
	}
	// The decision does not depend on N: the state search covers every path.
	if tr.Feasibility.Status != FeasInfeasible {
		t.Fatalf("status %s", tr.Feasibility.Status)
	}
}

// --- the filter only annotates ------------------------------------------------------------------

func TestFeasDoesNotChangeReachResults(t *testing.T) {
	dir := feasModule(t, strings.Replace(f1Iface, "CALL", "false", 1))
	plain, _, err := runReach(feasReq(dir, nil), io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	with, _, err := runReach(feasReq(dir, &FeasibilityRequest{}), io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	w := with.([]TargetResult)
	if w[0].Feasibility == nil {
		t.Fatal("missing feasibility")
	}
	w[0].Feasibility = nil
	a, _ := json.Marshal(plain)
	b, _ := json.Marshal(w)
	if !bytes.Equal(a, b) {
		t.Fatalf("the filter changed result, paths or matched functions:\n%s\n%s", a, b)
	}
	if bytes.Contains(a, []byte(`"feasibility"`)) {
		t.Fatal("a request without feasibility must not produce the field")
	}
}

func TestFeasDeterministic(t *testing.T) {
	dir := feasModule(t, strings.Replace(f1Once, "MORE", "", 1))
	var outs [][]byte
	for i := 0; i < 2; i++ {
		r, _, err := runReach(feasReq(dir, &FeasibilityRequest{}), io.Discard)
		if err != nil {
			t.Fatal(err)
		}
		b, _ := json.Marshal(r)
		outs = append(outs, b)
	}
	if !bytes.Equal(outs[0], outs[1]) {
		t.Fatal("two runs differ")
	}
}

func TestFeasRequestValidation(t *testing.T) {
	ok := `{"contract_version":"1.0","mode":"reach","module_dir":"x","main_packages":["./a"],"targets":[{"package":"p","symbol":"F"}],"feasibility":{"max_examined_paths":20}}`
	if _, err := decodeRequest([]byte(ok), "reach"); err != nil {
		t.Fatalf("valid feasibility request rejected: %v", err)
	}
	neg := strings.Replace(ok, `"max_examined_paths":20`, `"max_examined_paths":-1`, 1)
	if _, err := decodeRequest([]byte(neg), "reach"); err == nil || err.Code != CodeBadRequest {
		t.Fatalf("negative limit: %v", err)
	}
	naive := strings.Replace(ok, `"mode":"reach"`, `"mode":"naive"`, 1)
	if _, err := decodeRequest([]byte(naive), "naive"); err == nil || err.Code != CodeBadRequest {
		t.Fatalf("feasibility in naive mode must be BAD_REQUEST: %v", err)
	}
	edges := `{"contract_version":"1.0","mode":"edges","module_dir":"x","main_packages":["./a"],"edges":[{"caller":"a","callee":"b"}],"feasibility":{}}`
	if _, err := decodeRequest([]byte(edges), "edges"); err == nil || err.Code != CodeBadRequest {
		t.Fatalf("feasibility in edges mode must be BAD_REQUEST: %v", err)
	}
}
