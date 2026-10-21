package main

import (
	"fmt"
	"go/build"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/packages"
)

// buildEnv is the environment for `go list` (via go/packages): local toolchain, no cgo,
// no network, no inherited GOFLAGS.
func buildEnv(req *Request) []string {
	drop := map[string]bool{"GOTOOLCHAIN": true, "CGO_ENABLED": true, "GOPROXY": true, "GOFLAGS": true}
	set := []string{"GOTOOLCHAIN=local", "CGO_ENABLED=0", "GOPROXY=off"}
	if req.Build.GOOS != nil && *req.Build.GOOS != "" {
		drop["GOOS"] = true
		set = append(set, "GOOS="+*req.Build.GOOS)
	}
	if req.Build.GOARCH != nil && *req.Build.GOARCH != "" {
		drop["GOARCH"] = true
		set = append(set, "GOARCH="+*req.Build.GOARCH)
	}
	var env []string
	for _, kv := range os.Environ() {
		if k, _, _ := strings.Cut(kv, "="); !drop[k] {
			env = append(env, kv)
		}
	}
	return append(env, set...)
}

func moduleDirAbs(req *Request) (string, *Error) {
	dir, err := filepath.Abs(filepath.FromSlash(strings.ReplaceAll(req.ModuleDir, "\\", "/")))
	if err != nil {
		return "", errf(CodeBadRequest, "bad module_dir: "+err.Error())
	}
	if st, err := os.Stat(dir); err != nil || !st.IsDir() {
		return "", errf(CodeLoadFailed, "module_dir is not a directory: "+req.ModuleDir)
	}
	return dir, nil
}

// loadPackages loads the main packages and checks that every root is a main package.
// List and parse errors are LOAD_FAILED; type-checking errors are TYPE_ERRORS.
func loadPackages(req *Request, mode packages.LoadMode) ([]*packages.Package, string, *Error) {
	dir, e := moduleDirAbs(req)
	if e != nil {
		return nil, "", e
	}
	cfg := &packages.Config{Mode: mode, Dir: dir, Env: buildEnv(req), Tests: false}
	if len(req.Build.Tags) > 0 {
		cfg.BuildFlags = []string{"-tags=" + strings.Join(req.Build.Tags, ",")}
	}
	patterns := make([]string, len(req.MainPackages))
	for i, p := range req.MainPackages {
		patterns[i] = strings.ReplaceAll(p, "\\", "/")
	}
	pkgs, err := packages.Load(cfg, patterns...)
	if err != nil {
		return nil, "", errf(CodeLoadFailed, err.Error())
	}
	if len(pkgs) == 0 {
		return nil, "", errf(CodeLoadFailed, "no packages matched "+strings.Join(patterns, " "))
	}
	var loadErrs, typeErrs []string
	packages.Visit(pkgs, nil, func(p *packages.Package) {
		for _, pe := range p.Errors {
			msg := pe.Error()
			if pe.Kind == packages.TypeError {
				typeErrs = append(typeErrs, msg)
			} else {
				loadErrs = append(loadErrs, msg)
			}
		}
	})
	if len(loadErrs) > 0 {
		return nil, "", errf(CodeLoadFailed, summarise(loadErrs))
	}
	if len(typeErrs) > 0 {
		return nil, "", errf(CodeTypeErrors, summarise(typeErrs))
	}
	for _, p := range pkgs {
		if p.Name != "main" {
			return nil, "", errf(CodeLoadFailed, fmt.Sprintf("package %s is not a main package (name %q)", p.PkgPath, p.Name))
		}
	}
	return pkgs, dir, nil
}

func summarise(msgs []string) string {
	sort.Strings(msgs)
	if len(msgs) > 5 {
		return strings.Join(msgs[:5], "; ") + fmt.Sprintf("; ... (%d errors)", len(msgs))
	}
	return strings.Join(msgs, "; ")
}

// relativizer turns absolute file names into the CallPath form: module-relative with forward
// slashes, "$GOROOT/..." for the standard library, otherwise absolute with forward slashes.
type relativizer struct{ moduleDir, goroot string }

func newRelativizer(moduleDir string) relativizer {
	return relativizer{moduleDir: moduleDir, goroot: build.Default.GOROOT}
}

func (r relativizer) file(name string) string {
	if name == "" {
		return ""
	}
	if rel, ok := under(r.moduleDir, name); ok {
		return rel
	}
	if r.goroot != "" {
		if rel, ok := under(r.goroot, name); ok {
			return "$GOROOT/" + rel
		}
	}
	return filepath.ToSlash(name)
}

func under(dir, name string) (string, bool) {
	rel, err := filepath.Rel(dir, name)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
		return "", false
	}
	return filepath.ToSlash(rel), true
}

func countPackages(pkgs []*packages.Package) int {
	n := 0
	packages.Visit(pkgs, nil, func(*packages.Package) { n++ })
	return n
}
