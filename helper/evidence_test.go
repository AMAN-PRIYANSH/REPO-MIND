package main

import (
	"encoding/json"
	"io"
	"strings"
	"testing"
)

// CP10 unit tests: the opt-in ranking of examined paths (filter pass, then fewer DYNAMIC steps,
// then shorter), the kind of each DYNAMIC edge, and the promise that a request without
// rank_evidence and label_dynamic is answered exactly as before.

// Two routes to Vuln: a shorter one through an interface method call, and a longer one with
// static calls only. The shortest path is not the static one; ranking must pick the static one.
const rankMain = `package main

import "tm/lib"

type runner interface{ Run(string) string }
type impl struct{}

func (impl) Run(s string) string { return lib.Vuln(s) }

func a(s string) string { return b(s) }
func b(s string) string { return lib.Vuln(s) }

func use(f func(string) string, s string) string { return f(s) }

var fv = map[string]func(string) string{"v": lib.Vuln}

func viaValue(s string) string { return fv["v"](s) }

func main() {
	var r runner = impl{}
	println(r.Run("x"))
	println(a("y"))
	println(use(func(s string) string { return lib.Vuln(s) }, "z"))
	println(viaValue("w"))
}
`

func rankResult(t *testing.T, rank, label bool) TargetResult {
	t.Helper()
	dir := feasModule(t, rankMain)
	req := feasReq(dir, &FeasibilityRequest{MaxExaminedPaths: 20, RankEvidence: rank})
	req.LabelDynamic = label
	res, _, err := runReach(req, io.Discard)
	if err != nil {
		t.Fatalf("reach: %v", err)
	}
	tr := res.([]TargetResult)[0]
	if tr.Result != ResultPathFound || tr.Feasibility == nil {
		t.Fatalf("expected PATH_FOUND with a feasibility answer, got %+v", tr)
	}
	return tr
}

func countDyn(p *CallPath) int {
	n := 0
	for _, e := range p.Edges {
		if e.Kind == KindDynamic {
			n++
		}
	}
	return n
}

func TestRankEvidencePrefersFewerDynamicSteps(t *testing.T) {
	tr := rankResult(t, true, true)
	f := tr.Feasibility
	if f.Status != FeasFeasible || f.RankedPath == nil || f.RankedIndex == nil || f.RankRule == nil {
		b, _ := json.MarshalIndent(f, "", " ")
		t.Fatalf("want a FEASIBLE answer with a ranked path\n%s", b)
	}
	if *f.RankRule != RankFilterDynShortest {
		t.Fatalf("rank rule %q", *f.RankRule)
	}
	if countDyn(f.RankedPath) != 0 {
		t.Fatalf("ranked path has %d dynamic steps, a static route exists: %+v", countDyn(f.RankedPath), f.RankedPath)
	}
	if countDyn(f.EvidencePath) == 0 {
		t.Fatalf("test premise: the CP9 evidence path (shortest) should have a dynamic step: %+v", f.EvidencePath)
	}
	best := f.Examined[*f.RankedIndex]
	if best.FirstInfeasible != nil || best.DynamicSteps == nil || *best.DynamicSteps != 0 {
		t.Fatalf("ranked index points at %+v", best)
	}
	for i, ex := range f.Examined {
		if ex.DynamicSteps == nil {
			t.Fatalf("examined path %d has no dynamic_steps", i)
		}
		if ex.FirstInfeasible == nil && (*ex.DynamicSteps < 0 ||
			(*ex.DynamicSteps == 0 && ex.Length < best.Length) || (i < *f.RankedIndex && *ex.DynamicSteps == 0 && ex.Length == best.Length)) {
			t.Fatalf("examined path %d beats the ranked one: %+v vs %+v", i, ex, best)
		}
	}
}

func TestLabelDynamicKinds(t *testing.T) {
	tr := rankResult(t, true, true)
	kinds := map[string]bool{}
	seen := func(p *CallPath) {
		for _, e := range p.Edges {
			switch {
			case e.Kind == KindDynamic && e.DynamicKind == "":
				t.Fatalf("DYNAMIC edge without dynamic_kind: %+v", e)
			case e.Kind == KindStatic && e.DynamicKind != "":
				t.Fatalf("STATIC edge with dynamic_kind: %+v", e)
			}
			if e.DynamicKind != "" {
				kinds[e.DynamicKind+" "+e.Callee] = true
			}
		}
	}
	for i := range tr.Paths {
		seen(&tr.Paths[i])
	}
	seen(tr.Feasibility.EvidencePath)
	seen(tr.Feasibility.RankedPath)
	// every route of rankMain, with its dynamic kind, from the full graph
	a, err := analyse(feasReq(feasModule(t, rankMain), nil), io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]string{}
	for from, es := range a.g.out {
		for _, e := range es {
			if e.Kind == KindDynamic && strings.HasPrefix(a.g.nodes[from].Name(), "tm/cmd/app.") {
				got[a.g.nodes[from].Name()+" -> "+a.g.nodes[e.To].Name()] = a.g.dyn[e]
			}
		}
	}
	want := map[string]string{
		"tm/cmd/app.main -> tm/cmd/app.impl.Run": DynInterfaceMethod,
		"tm/cmd/app.use -> tm/cmd/app.main$1":    DynClosureViaParam,
		"tm/cmd/app.viaValue -> tm/lib.Vuln":     DynFunctionValue,
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s: dynamic kind %q, want %q (all: %v)", k, got[k], v, got)
		}
	}
}

func TestNoRankNoLabelIsTheCP9Output(t *testing.T) {
	plain := rankResult(t, false, false)
	b, _ := json.Marshal(plain)
	for _, key := range []string{"dynamic_kind", "dynamic_steps", "ranked_path", "ranked_index", "rank_rule"} {
		if strings.Contains(string(b), `"`+key+`"`) {
			t.Fatalf("%s present without the CP10 options: %s", key, b)
		}
	}
	ranked := rankResult(t, true, true)
	// the CP9 fields are unchanged by ranking (ignoring the added labels)
	strip := func(tr TargetResult) string {
		tr.Feasibility.RankRule, tr.Feasibility.RankedPath, tr.Feasibility.RankedIndex = nil, nil, nil
		for i := range tr.Feasibility.Examined {
			tr.Feasibility.Examined[i].DynamicSteps = nil
		}
		b, _ := json.Marshal(tr)
		s := string(b)
		for _, k := range []string{DynInterfaceMethod, DynClosureViaParam, DynFunctionValue, DynMixed} {
			s = strings.ReplaceAll(s, `,"dynamic_kind":"`+k+`"`, "")
		}
		return s
	}
	if strip(ranked) != string(b) {
		t.Fatalf("ranking changed CP9 output:\n%s\n%s", strip(ranked), b)
	}
}
