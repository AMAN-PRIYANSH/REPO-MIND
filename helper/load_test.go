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

// TestReachTargetNotFoundIsNotNoPath checks the two symbol-lookup rules from the interfaces
// contract (section 2): a missing symbol in a loaded package is always TARGET_NOT_FOUND
// (never NO_PATH), in both reach and naive mode. A target whose package is not part of the
// loaded program at all is different: in reach mode (the exception added after the CP2
// review) it is NO_PATH with details.package_not_in_program=true, because no code from an
// unimported package can run; naive mode (the unsafe negative control) is unchanged and
// still reports it as TARGET_NOT_FOUND.
func TestReachTargetNotFoundIsNotNoPath(t *testing.T) {
	dir := tempModule(t, map[string]string{
		"lib/lib.go":      libSrc,
		"other/other.go":  "package other\n\nfunc X() {}\n",
		"cmd/app/main.go": "package main\n\nimport \"tm/lib\"\n\nfunc main() { _ = lib.T{} }\n",
	})
	targets := []Target{
		{"tm/lib", "Unused"},  // exists, never called
		{"tm/lib", "Missing"}, // not declared
		{"tm/other", "X"},     // package not imported
		{"tm/lib", "T.M"},     // method exists, never called
		{"tm/lib", "a.b.c"},   // bad form
	}
	type want struct{ result, code string }
	cases := map[string][]want{
		"reach": {
			{ResultNoPath, ""}, {ResultError, CodeTargetNotFound}, {ResultNoPath, ""},
			{ResultNoPath, ""}, {ResultError, CodeUnsupportedForm},
		},
		"naive": {
			{ResultNoPath, ""}, {ResultError, CodeTargetNotFound}, {ResultError, CodeTargetNotFound},
			{ResultNoPath, ""}, {ResultError, CodeUnsupportedForm},
		},
	}
	for mode, want := range cases {
		run := runReach
		if mode == "naive" {
			run = runNaive
		}
		res, _, err := run(reachReq(dir, mode, targets...), io.Discard)
		if err != nil {
			t.Fatal(err)
		}
		for i, r := range res.([]TargetResult) {
			code := ""
			if r.Error != nil {
				code = r.Error.Code
			}
			if r.Result != want[i].result || code != want[i].code {
				t.Errorf("%s target %v: %s %s; want %s %s", mode, r.Target, r.Result, code, want[i].result, want[i].code)
			}
			wantPkgNotInProgram := mode == "reach" && i == 2
			if r.PackageNotInProgram != wantPkgNotInProgram {
				t.Errorf("%s target %v: package_not_in_program=%v; want %v", mode, r.Target, r.PackageNotInProgram, wantPkgNotInProgram)
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
