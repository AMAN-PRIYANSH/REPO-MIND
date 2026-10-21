package main

import (
	"io"
	"os"
	"path/filepath"
	"testing"
)

// tempModule writes a module "tm" with the given files and returns its directory.
func tempModule(t *testing.T, files map[string]string) string {
	t.Helper()
	dir := t.TempDir()
	files["go.mod"] = "module tm\n\ngo 1.21\n"
	for name, src := range files {
		p := filepath.Join(dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(src), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func reachReq(dir, mode string, targets ...Target) *Request {
	return &Request{ContractVersion: "1.0", Mode: mode, ModuleDir: dir, MainPackages: []string{"./cmd/app"},
		Targets: targets, Limits: Limits{MaxPathsPerTarget: 3, MaxPathLength: 40}}
}

const libSrc = `package lib

func Vuln() int { return 1 }

func Unused() int { return Vuln() }

type T struct{}

func (T) M() int { return Vuln() }
`

func TestLoadErrorsAreClassified(t *testing.T) {
	typeErr := tempModule(t, map[string]string{"cmd/app/main.go": "package main\n\nfunc main() { var x int = \"s\"; _ = x }\n"})
	if _, _, err := runReach(reachReq(typeErr, "reach", Target{"tm/lib", "Vuln"}), io.Discard); err == nil || err.Code != CodeTypeErrors {
		t.Errorf("type error: got %v; want %s", err, CodeTypeErrors)
	}
	parseErr := tempModule(t, map[string]string{"cmd/app/main.go": "package main\n\nfunc main( {\n"})
	if _, _, err := runReach(reachReq(parseErr, "reach", Target{"tm/lib", "Vuln"}), io.Discard); err == nil || err.Code != CodeLoadFailed {
		t.Errorf("parse error: got %v; want %s", err, CodeLoadFailed)
	}
	notMain := tempModule(t, map[string]string{"cmd/app/lib.go": "package app\n"})
	if _, _, err := runReach(reachReq(notMain, "reach", Target{"tm/lib", "Vuln"}), io.Discard); err == nil || err.Code != CodeLoadFailed {
		t.Errorf("not main: got %v; want %s", err, CodeLoadFailed)
	}
	if _, _, err := runNaive(reachReq(typeErr, "naive", Target{"tm/lib", "Vuln"}), io.Discard); err != nil {
		t.Errorf("naive does not type-check, so a type error must not fail it: %v", err)
	}
}

func TestReachTargetNotFoundIsNotNoPath(t *testing.T) {
	dir := tempModule(t, map[string]string{
		"lib/lib.go":      libSrc,
		"other/other.go":  "package other\n\nfunc X() {}\n",
		"cmd/app/main.go": "package main\n\nimport \"tm/lib\"\n\nfunc main() { _ = lib.T{} }\n",
	})
	for _, mode := range []string{"reach", "naive"} {
		run := runReach
		if mode == "naive" {
			run = runNaive
		}
		res, _, err := run(reachReq(dir, mode,
			Target{"tm/lib", "Unused"},  // exists, never called
			Target{"tm/lib", "Missing"}, // not declared
			Target{"tm/other", "X"},     // package not imported
			Target{"tm/lib", "T.M"},     // method exists, never called
			Target{"tm/lib", "a.b.c"},   // bad form
		), io.Discard)
		if err != nil {
			t.Fatal(err)
		}
		want := []struct{ result, code string }{
			{ResultNoPath, ""}, {ResultError, CodeTargetNotFound}, {ResultError, CodeTargetNotFound},
			{ResultNoPath, ""}, {ResultError, CodeUnsupportedForm},
		}
		for i, r := range res.([]TargetResult) {
			code := ""
			if r.Error != nil {
				code = r.Error.Code
			}
			if r.Result != want[i].result || code != want[i].code {
				t.Errorf("%s target %v: %s %s; want %s %s", mode, r.Target, r.Result, code, want[i].result, want[i].code)
			}
		}
	}
}

func TestReachFindsInitPaths(t *testing.T) {
	dir := tempModule(t, map[string]string{
		"lib/lib.go":      libSrc,
		"dep/dep.go":      "package dep\n\nimport \"tm/lib\"\n\nvar V = lib.Vuln()\n",
		"cmd/app/main.go": "package main\n\nimport _ \"tm/dep\"\n\nfunc main() {}\n",
	})
	res, _, err := runReach(reachReq(dir, "reach", Target{"tm/lib", "Vuln"}), io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	r := res.([]TargetResult)[0]
	if r.Result != ResultPathFound || r.Paths[0].Entry.Symbol != "init" {
		t.Fatalf("package-level initialiser path not found from init root: %+v", r)
	}
	last := r.Paths[0].Edges[len(r.Paths[0].Edges)-1]
	if last.Callee != "tm/lib.Vuln" || last.CallSite != (Site{File: "dep/dep.go", Line: 5}) {
		t.Fatalf("last edge %+v", last)
	}
}
