package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
)

// liftFixtures is the CP5b fixture module (truth by construction, observed by these tests).
func liftFixtures(t *testing.T) string {
	t.Helper()
	dir, err := filepath.Abs("../fixtures/lifting")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "go.mod")); err != nil {
		t.Skip("fixtures/lifting not found")
	}
	return dir
}

func queryRequest(mode, dir string, extra string, targets ...Target) string {
	tj, _ := json.Marshal(targets)
	return fmt.Sprintf(`{"contract_version":"1.0","mode":%q,"module_dir":%q,"targets":%s%s}`, mode, filepath.ToSlash(dir), tj, extra)
}

func liftResults(t *testing.T, body string) ([]LiftResult, Response) {
	t.Helper()
	resp, code := runHelper(t, "lift", "--request", writeReq(t, body))
	if !resp.OK || code != 0 {
		t.Fatalf("lift failed: %+v", resp.Error)
	}
	raw, _ := json.Marshal(resp.Results)
	var out []LiftResult
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out, resp
}

func entrySymbols(rr LiftRuleResult) []string {
	out := []string{}
	for _, e := range rr.Entries {
		out = append(out, e.Symbol)
	}
	sort.Strings(out)
	return out
}

func lt(pkg, sym string) Target { return Target{Package: "vtlift/" + pkg, Symbol: sym} }

func TestLiftFixtureOutcomes(t *testing.T) {
	dir := liftFixtures(t)
	cases := []struct {
		name          string
		seed          Target
		status        string
		nearest, all  []string
		dynamic       bool
		depthLimitHit bool
		limit         int
		errCode       string
	}{
		{name: "private helper", seed: lt("private_helper", "parse"), status: LiftLifted, nearest: []string{"Parse"}, all: []string{"Parse"}},
		{name: "interface call", seed: lt("interface_call", "impl.run"), status: LiftLifted, nearest: []string{"Do"}, all: []string{"Do"}, dynamic: true},
		{name: "function value", seed: lt("func_value", "step"), status: LiftLifted, nearest: []string{"Dispatch"}, all: []string{"Dispatch"}, dynamic: true},
		{name: "method value", seed: lt("method_value", "tool.work"), status: LiftLifted, nearest: []string{"Use"}, all: []string{"Use"}},
		{name: "exported method of unexported type is not an entry", seed: lt("unexported_type", "impl.work"), status: LiftLifted, nearest: []string{"Wrap"}, all: []string{"Wrap"}},
		{name: "internal package", seed: lt("internal_pkg/internal/core", "Core"), status: LiftLifted, nearest: []string{"Public"}, all: []string{"Public"}},
		{name: "only init calls it", seed: lt("root_only", "orphan"), status: LiftRootOnly},
		{name: "never called", seed: lt("never_called", "dead"), status: LiftRootOnly},
		{name: "only main calls it", seed: lt("main_caller", "run"), status: LiftRootOnly},
		{name: "already exported", seed: lt("already_exported", "Parse"), status: LiftAlreadyExported, nearest: []string{"Parse"}, all: []string{"Parse"}},
		{name: "diamond separates the rules", seed: lt("diamond", "sink"), status: LiftLifted, nearest: []string{"Left", "Right"}, all: []string{"Left", "Right", "Top"}},
		{name: "closure folds into its function", seed: lt("closure", "inner"), status: LiftLifted, nearest: []string{"Run"}, all: []string{"Run"}},
		{name: "generic exported caller", seed: lt("generic_seed", "priv"), status: LiftLifted, nearest: []string{"Each"}, all: []string{"Each"}},
		{name: "generic seed unsupported", seed: lt("generic_seed", "Map"), status: LiftError, errCode: CodeUnsupportedForm},
		{name: "unknown symbol", seed: lt("private_helper", "Nope"), status: LiftError, errCode: CodeTargetNotFound},
		{name: "depth limit is reported, not a silent ROOT_ONLY", seed: lt("chain", "a"), status: LiftRootOnly, depthLimitHit: true, limit: 2},
		{name: "depth limit deep enough", seed: lt("chain", "a"), status: LiftLifted, nearest: []string{"Top"}, all: []string{"Top"}, limit: 4},
	}
	for _, c := range cases {
		extra := ""
		if c.limit > 0 {
			extra = fmt.Sprintf(`,"limits":{"max_lift_depth":%d}`, c.limit)
		}
		res, _ := liftResults(t, queryRequest("lift", dir, extra, c.seed))
		r := res[0]
		if r.Status != c.status {
			t.Errorf("%s: status %s, want %s", c.name, r.Status, c.status)
			continue
		}
		if c.errCode != "" {
			if r.Error == nil || r.Error.Code != c.errCode {
				t.Errorf("%s: error %+v, want %s", c.name, r.Error, c.errCode)
			}
			continue
		}
		if got := entrySymbols(r.Rules[RuleNearest]); !reflect.DeepEqual(got, orEmpty(c.nearest)) {
			t.Errorf("%s: NEAREST %v, want %v", c.name, got, c.nearest)
		}
		if got := entrySymbols(r.Rules[RuleAll]); !reflect.DeepEqual(got, orEmpty(c.all)) {
			t.Errorf("%s: ALL %v, want %v", c.name, got, c.all)
		}
		if c.dynamic {
			if e := r.Rules[RuleNearest].Entries[0]; !e.Dynamic {
				t.Errorf("%s: example path should contain a DYNAMIC edge: %+v", c.name, e.Path.Edges)
			}
		}
		if got := r.Rules[RuleAll].DepthLimitReached; got != c.depthLimitHit {
			t.Errorf("%s: depth_limit_reached %v, want %v", c.name, got, c.depthLimitHit)
		}
	}
}

func orEmpty(s []string) []string {
	if s == nil {
		return []string{}
	}
	return s
}

func TestLiftPathEndsAtSeedAndStartsAtEntry(t *testing.T) {
	dir := liftFixtures(t)
	res, _ := liftResults(t, queryRequest("lift", dir, "", lt("diamond", "sink")))
	for rule, rr := range res[0].Rules {
		for _, e := range rr.Entries {
			edges := e.Path.Edges
			if len(edges) != e.Depth || len(edges) == 0 {
				t.Fatalf("%s %s: depth %d but %d edges", rule, e.Symbol, e.Depth, len(edges))
			}
			if !strings.HasSuffix(edges[0].Caller, "."+e.Symbol) || !strings.HasSuffix(edges[len(edges)-1].Callee, ".sink") {
				t.Errorf("%s %s: path does not run entry -> seed: %+v", rule, e.Symbol, edges)
			}
			for i := 1; i < len(edges); i++ {
				if edges[i].Caller != edges[i-1].Callee {
					t.Errorf("%s %s: path is not contiguous at edge %d", rule, e.Symbol, i)
				}
			}
			if e.Path.Entry.Symbol != e.Symbol || e.Path.Target.Symbol != "sink" {
				t.Errorf("%s %s: entry/target fields wrong: %+v", rule, e.Symbol, e.Path)
			}
		}
	}
}

func TestLiftSingleRule(t *testing.T) {
	dir := liftFixtures(t)
	res, _ := liftResults(t, queryRequest("lift", dir, `,"lift_rules":["NEAREST"]`, lt("diamond", "sink")))
	if _, ok := res[0].Rules[RuleAll]; ok || len(res[0].Rules) != 1 {
		t.Errorf("only NEAREST was requested: %v", res[0].Rules)
	}
	resp, _ := runHelper(t, "lift", "--request", writeReq(t, queryRequest("lift", dir, `,"lift_rules":["SOME"]`, lt("diamond", "sink"))))
	if resp.OK || resp.Error.Code != CodeBadRequest {
		t.Errorf("unknown rule must be BAD_REQUEST: %+v", resp.Error)
	}
}

func TestLiftDeterministic(t *testing.T) {
	dir := liftFixtures(t)
	body := queryRequest("lift", dir, "", lt("diamond", "sink"), lt("interface_call", "impl.run"), lt("chain", "a"))
	var first []byte
	for i := 0; i < 3; i++ {
		res, _ := liftResults(t, body)
		b, _ := json.Marshal(res)
		if first == nil {
			first = b
		} else if string(first) != string(b) {
			t.Fatalf("run %d differs:\n%s\n%s", i, first, b)
		}
	}
}

func TestLiftPackageNotInProgramAndLoadInfo(t *testing.T) {
	dir := liftFixtures(t)
	res, resp := liftResults(t, queryRequest("lift", dir, "", Target{Package: "not/there", Symbol: "X"}))
	if res[0].Status != LiftNotInProgram || !res[0].PackageNotInProgram {
		t.Errorf("got %+v", res[0])
	}
	if resp.Load == nil || resp.Load.Mode != "LIBRARY" || resp.Load.PackagesSkipped != 0 || resp.Load.PackagesMatched == 0 {
		t.Errorf("load info: %+v", resp.Load)
	}
}

// brokenModule has one good package, one with a syntax error, and one importing the broken one.
func brokenModule(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	files := map[string]string{
		"go.mod":       "module bm\n\ngo 1.21\n",
		"good/good.go": "package good\n\nfunc Exported() int { return helper() }\n\nfunc helper() int { return 1 }\n",
		"bad/bad.go":   "package bad\n\nfunc Broken( {\n",
		"user/user.go": "package user\n\nimport \"bm/bad\"\n\nvar _ = bad.Broken\n",
	}
	for name, body := range files {
		p := filepath.Join(dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func TestLiftSkipsBrokenPackagesAndCountsThem(t *testing.T) {
	dir := brokenModule(t)
	res, resp := liftResults(t, queryRequest("lift", dir, "",
		Target{Package: "bm/good", Symbol: "helper"}, Target{Package: "bm/user", Symbol: "X"}, Target{Package: "bm/bad", Symbol: "Broken"}))
	if resp.Load.PackagesSkipped != 2 || resp.Load.PackagesMatched != 3 || len(resp.Load.FirstErrors) != 2 {
		t.Errorf("load info: %+v", resp.Load)
	}
	if res[0].Status != LiftLifted {
		t.Errorf("good package should still lift: %+v", res[0])
	}
	for _, r := range res[1:] {
		if r.Status != LiftError || r.Error == nil || r.Error.Code != CodePackageUnloaded {
			t.Errorf("a skipped package must report %s, not look absent: %+v", CodePackageUnloaded, r)
		}
	}
}

func TestLiftLoadFailedWhenNothingLoads(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "go.mod"), []byte("module nl\n\ngo 1.21\n"), 0o644)
	os.WriteFile(filepath.Join(dir, "a.go"), []byte("package a\n\nfunc F( {\n"), 0o644)
	resp, code := runHelper(t, "lift", "--request", writeReq(t, queryRequest("lift", dir, "", Target{Package: "nl", Symbol: "F"})))
	if resp.OK || code != 1 || resp.Error.Code != CodeLoadFailed || strings.Contains(resp.Error.Message, "\n") {
		t.Errorf("want LOAD_FAILED with a one-line message: %+v", resp.Error)
	}
}

func TestCallersAndCallees(t *testing.T) {
	dir := liftFixtures(t)
	resp, _ := runHelper(t, "callers", "--request", writeReq(t, queryRequest("callers", dir, `,"limits":{"max_hops":2}`, lt("diamond", "sink"))))
	raw, _ := json.Marshal(resp.Results)
	var res []NeighborResult
	json.Unmarshal(raw, &res)
	hops := map[int][]string{}
	for _, e := range res[0].Edges {
		hops[e.Hop] = append(hops[e.Hop], e.Other.Symbol)
	}
	for h := range hops {
		sort.Strings(hops[h])
	}
	want := map[int][]string{1: {"left", "right"}, 2: {"Left", "Right"}}
	if res[0].Result != NeighborFound || !reflect.DeepEqual(hops, want) {
		t.Errorf("callers 2 hops: %v (%s), want %v", hops, res[0].Result, want)
	}
	for _, e := range res[0].Edges {
		if e.CallSite.File == "" || e.CallSite.Line == 0 {
			t.Errorf("a source-level edge must carry its call site: %+v", e)
		}
	}
	// One hop only reaches the direct callers.
	resp, _ = runHelper(t, "callers", "--request", writeReq(t, queryRequest("callers", dir, "", lt("diamond", "sink"))))
	raw, _ = json.Marshal(resp.Results)
	json.Unmarshal(raw, &res)
	if len(res[0].Edges) != 2 {
		t.Errorf("one hop: %+v", res[0].Edges)
	}
	// Callees of Top are Left and Right; dynamic edges are labelled.
	resp, _ = runHelper(t, "callees", "--request", writeReq(t, queryRequest("callees", dir, "", lt("diamond", "Top"), lt("interface_call", "Do"), lt("never_called", "dead"))))
	raw, _ = json.Marshal(resp.Results)
	json.Unmarshal(raw, &res)
	if names := []string{res[0].Edges[0].Other.Symbol, res[0].Edges[1].Other.Symbol}; !reflect.DeepEqual(names, []string{"Left", "Right"}) {
		t.Errorf("callees of Top: %v", names)
	}
	foundDynamic := false
	for _, e := range res[1].Edges {
		if e.Kind == KindDynamic {
			foundDynamic = true
		}
	}
	if !foundDynamic {
		t.Errorf("interface call must show a DYNAMIC callee edge: %+v", res[1].Edges)
	}
	if res[2].Result != NeighborNone || len(res[2].Edges) != 0 {
		t.Errorf("a leaf has no callees in the module: %+v", res[2])
	}
}

func TestNeighborsTruncateAndFilterExternal(t *testing.T) {
	dir := liftFixtures(t)
	resp, _ := runHelper(t, "callees", "--request", writeReq(t, queryRequest("callees", dir, `,"limits":{"max_results":1}`, lt("diamond", "Top"))))
	raw, _ := json.Marshal(resp.Results)
	var res []NeighborResult
	json.Unmarshal(raw, &res)
	if len(res[0].Edges) != 1 || !res[0].Truncated {
		t.Errorf("max_results 1 must truncate and say so: %+v", res[0])
	}
	// Without `external` a call into the standard library is not reported; with it, it is.
	body := func(extra string) string {
		return queryRequest("callees", dir, extra, lt("private_helper", "parse"))
	}
	resp, _ = runHelper(t, "callees", "--request", writeReq(t, body("")))
	raw, _ = json.Marshal(resp.Results)
	json.Unmarshal(raw, &res)
	inModule := len(res[0].Edges)
	resp, _ = runHelper(t, "callees", "--request", writeReq(t, body(`,"external":true`)))
	raw, _ = json.Marshal(resp.Results)
	json.Unmarshal(raw, &res)
	if inModule != 0 || len(res[0].Edges) < inModule {
		t.Errorf("in-module %d, with external %d", inModule, len(res[0].Edges))
	}
}

func TestQueryRequestValidation(t *testing.T) {
	for name, body := range map[string]string{
		"no module_dir": `{"contract_version":"1.0","mode":"lift","targets":[{"package":"p","symbol":"F"}]}`,
		"no targets":    `{"contract_version":"1.0","mode":"callers","module_dir":"."}`,
		"negative hops": `{"contract_version":"1.0","mode":"callees","module_dir":".","targets":[{"package":"p","symbol":"F"}],"limits":{"max_hops":-1}}`,
	} {
		mode := "lift"
		if strings.Contains(body, `"callers"`) {
			mode = "callers"
		} else if strings.Contains(body, `"callees"`) {
			mode = "callees"
		}
		resp, _ := runHelper(t, mode, "--request", writeReq(t, body))
		if resp.OK || resp.Error.Code != CodeBadRequest {
			t.Errorf("%s: %+v", name, resp.Error)
		}
	}
}

// typecheck parses one source file and returns its package scope.
func typecheck(t *testing.T, path, src string) *types.Package {
	t.Helper()
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "x.go", src, 0)
	if err != nil {
		t.Fatal(err)
	}
	pkg, err := (&types.Config{Importer: importer.Default()}).Check(path, fset, []*ast.File{f}, nil)
	if err != nil {
		t.Fatal(err)
	}
	return pkg
}

func TestIsEntryPoint(t *testing.T) {
	src := `package p
func Exported() {}
func unexported() {}
type Pub struct{}
func (Pub) M() {}
func (Pub) m() {}
func (*Pub) PM() {}
type priv struct{}
func (priv) M() {}
func Gen[T any](x T) T { return x }
`
	cases := []struct {
		path, name, recv string
		want             bool
	}{
		{"ex.com/p", "Exported", "", true},
		{"ex.com/p", "unexported", "", false},
		{"ex.com/p", "M", "Pub", true},
		{"ex.com/p", "m", "Pub", false},
		{"ex.com/p", "PM", "Pub", true},
		{"ex.com/p", "M", "priv", false},
		{"ex.com/p", "Gen", "", true},
		{"ex.com/internal/p", "Exported", "", false},
		{"ex.com/p/internal", "Exported", "", false},
		{"internal/p", "Exported", "", false},
		{"ex.com/internals/p", "Exported", "", true}, // "internals" is not "internal"
	}
	for _, c := range cases {
		pkg := typecheck(t, c.path, src)
		var fn *types.Func
		if c.recv == "" {
			fn = pkg.Scope().Lookup(c.name).(*types.Func)
		} else {
			named := pkg.Scope().Lookup(c.recv).Type().(*types.Named)
			for i := 0; i < named.NumMethods(); i++ {
				if named.Method(i).Name() == c.name {
					fn = named.Method(i)
				}
			}
		}
		if got := isEntryPoint(fn); got != c.want {
			t.Errorf("%s %s.%s: isEntryPoint = %v, want %v", c.path, c.recv, c.name, got, c.want)
		}
	}
	main := typecheck(t, "ex.com/cmd/tool", strings.Replace(src, "package p", "package main", 1))
	if isEntryPoint(main.Scope().Lookup("Exported").(*types.Func)) {
		t.Error("an exported function of package main is not an entry point")
	}
	pkg := typecheck(t, "ex.com/p", src)
	if !isGenericDecl(pkg.Scope().Lookup("Gen").(*types.Func)) || isGenericDecl(pkg.Scope().Lookup("Exported").(*types.Func)) {
		t.Error("isGenericDecl wrong")
	}
	if got := objSymbol(pkg.Scope().Lookup("Pub").Type().(*types.Named).Method(0)); !strings.HasPrefix(got, "Pub.") {
		t.Errorf("objSymbol = %q", got)
	}
}

// App mode: with main_packages the roots are main and init (as in reach), and the module under study
// is the main packages' own module, so a caller in package main is found.
func TestQueryModesInAppMode(t *testing.T) {
	dir, err := filepath.Abs("../fixtures/reachability")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "go.mod")); err != nil {
		t.Skip("fixtures/reachability not found")
	}
	body := fmt.Sprintf(`{"contract_version":"1.0","mode":"callers","module_dir":%q,"main_packages":["./cmd/direct_call"],"targets":[{"package":"vtfixtures/vulnlib","symbol":"Parse"}]}`, filepath.ToSlash(dir))
	resp, _ := runHelper(t, "callers", "--request", writeReq(t, body))
	if !resp.OK || resp.Load == nil || resp.Load.Mode != "APP" {
		t.Fatalf("app mode: %+v %+v", resp.Error, resp.Load)
	}
	raw, _ := json.Marshal(resp.Results)
	var res []NeighborResult
	json.Unmarshal(raw, &res)
	if res[0].Result != NeighborFound || len(res[0].Edges) != 1 || res[0].Edges[0].Other.Symbol != "main" ||
		res[0].Edges[0].CallSite.File != "cmd/direct_call/main.go" || res[0].Edges[0].CallSite.Line != 10 {
		t.Errorf("callers of Parse in app mode: %+v", res[0])
	}
	// lift: Parse is exported, so it lifts to itself even though its only caller is main (never an entry point).
	body = strings.Replace(strings.Replace(body, `"callers"`, `"lift"`, 1), `"mode":"callers"`, `"mode":"lift"`, 1)
	lr, _ := runHelper(t, "lift", "--request", writeReq(t, body))
	raw, _ = json.Marshal(lr.Results)
	var lifts []LiftResult
	json.Unmarshal(raw, &lifts)
	if !lr.OK || lifts[0].Status != LiftAlreadyExported {
		t.Errorf("lift in app mode: %+v %+v", lr.Error, lifts)
	}
	// A main package that does not exist stays a LOAD_FAILED.
	bad := fmt.Sprintf(`{"contract_version":"1.0","mode":"callees","module_dir":%q,"main_packages":["./cmd/nope"],"targets":[{"package":"vtfixtures/vulnlib","symbol":"Parse"}]}`, filepath.ToSlash(dir))
	br, code := runHelper(t, "callees", "--request", writeReq(t, bad))
	if br.OK || code != 1 || br.Error.Code != CodeLoadFailed {
		t.Errorf("missing main package: %+v", br.Error)
	}
}
