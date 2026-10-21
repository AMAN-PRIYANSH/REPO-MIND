// Command vt-helper is VulnTrace's Go analysis helper.
//
//	vt-helper <mode> --request <request.json>
//
// It writes exactly one JSON object to stdout; logs go to stderr. It never
// accesses the network and never runs code from the analysed module.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"runtime"
	"runtime/debug"
	"strings"
	"time"
)

type modeFunc func(req *Request, stderr io.Writer) (any, *Stats, *Error)

// handlers maps each CP2 mode to its implementation (lift arrives in CP5).
var handlers = map[string]modeFunc{
	"funcs": func(req *Request, _ io.Writer) (any, *Stats, *Error) { r, err := runFuncs(req); return r, nil, err },
	"reach": runReach,
	"edges": runEdges,
	"naive": runNaive,
}

func main() { os.Exit(run(os.Args[1:], os.Stdout, os.Stderr)) }

// run returns 0 when the response has ok=true, 1 otherwise.
func run(args []string, stdout, stderr io.Writer) int {
	mode := ""
	if len(args) > 0 {
		mode = args[0]
	}
	resp := handle(args, stderr)
	resp.ContractVersion = ContractVersion
	resp.Mode = mode
	enc := json.NewEncoder(stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(resp); err != nil {
		fmt.Fprintln(stderr, "vt-helper: cannot write response:", err)
		return 1
	}
	if resp.OK {
		return 0
	}
	return 1
}

func handle(args []string, stderr io.Writer) (resp *Response) {
	start := time.Now()
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(stderr, "vt-helper: panic: %v\n%s", r, debug.Stack())
			resp = &Response{Error: errf(CodeInternal, fmt.Sprint(r))}
		}
	}()
	req, err := parseArgs(args)
	if err != nil {
		return &Response{Error: err}
	}
	results, stats, err := handlers[req.Mode](req, stderr)
	if err != nil {
		return &Response{Error: err}
	}
	if stats == nil {
		stats = &Stats{}
	}
	stats.DurationMS = time.Since(start).Milliseconds()
	stats.PeakRSSKB = peakRSSKB()
	return &Response{OK: true, Toolchain: toolchain(req), Results: results, Stats: stats}
}

func parseArgs(args []string) (*Request, *Error) {
	if len(args) == 0 {
		return nil, errf(CodeBadRequest, "usage: vt-helper <funcs|reach|edges|naive> --request <file>")
	}
	mode := args[0]
	if handlers[mode] == nil {
		return nil, errf(CodeBadRequest, fmt.Sprintf("unknown or unsupported mode %q (CP2 modes: funcs, reach, edges, naive)", mode))
	}
	fs := flag.NewFlagSet("vt-helper", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	reqPath := fs.String("request", "", "request JSON file")
	if err := fs.Parse(args[1:]); err != nil || *reqPath == "" || fs.NArg() != 0 {
		return nil, errf(CodeBadRequest, "expected exactly: vt-helper "+mode+" --request <file>")
	}
	data, err := os.ReadFile(*reqPath)
	if err != nil {
		return nil, errf(CodeBadRequest, "cannot read request: "+err.Error())
	}
	return decodeRequest(data, mode)
}

func decodeRequest(data []byte, mode string) (*Request, *Error) {
	var probe struct {
		ContractVersion *string `json:"contract_version"`
	}
	if err := json.Unmarshal(data, &probe); err != nil {
		return nil, errf(CodeBadRequest, "request is not a JSON object: "+err.Error())
	}
	if probe.ContractVersion == nil {
		return nil, errf(CodeBadRequest, "missing contract_version")
	}
	if major(*probe.ContractVersion) != major(ContractVersion) {
		return nil, errf(CodeContractMismatch, fmt.Sprintf("request contract_version %q, helper supports %q", *probe.ContractVersion, ContractVersion))
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var req Request
	if err := dec.Decode(&req); err != nil {
		return nil, errf(CodeBadRequest, "invalid request: "+err.Error())
	}
	if req.Mode != mode {
		return nil, errf(CodeBadRequest, fmt.Sprintf("request mode %q does not match command-line mode %q", req.Mode, mode))
	}
	if err := validate(&req); err != nil {
		return nil, err
	}
	return &req, nil
}

func major(v string) string { return strings.SplitN(v, ".", 2)[0] }

func validate(req *Request) *Error {
	need := func(ok bool, what string) *Error {
		if ok {
			return nil
		}
		return errf(CodeBadRequest, req.Mode+" request needs "+what)
	}
	switch req.Mode {
	case "funcs":
		return need(len(req.Files) > 0, "a non-empty files list")
	case "reach", "naive", "edges":
		if e := need(req.ModuleDir != "", "module_dir"); e != nil {
			return e
		}
		if e := need(len(req.MainPackages) > 0, "a non-empty main_packages list"); e != nil {
			return e
		}
		if req.Mode == "edges" {
			return need(len(req.Edges) > 0, "a non-empty edges list")
		}
		if e := need(len(req.Targets) > 0, "a non-empty targets list"); e != nil {
			return e
		}
		if req.Limits.MaxPathsPerTarget < 0 || req.Limits.MaxPathLength < 0 {
			return errf(CodeBadRequest, "limits must not be negative")
		}
		if req.Limits.MaxPathsPerTarget == 0 {
			req.Limits.MaxPathsPerTarget = defaultMaxPaths
		}
		if req.Limits.MaxPathLength == 0 {
			req.Limits.MaxPathLength = defaultMaxPathLength
		}
	}
	return nil
}

func toolchain(req *Request) *Toolchain {
	tc := &Toolchain{GoVersion: runtime.Version(), GOOS: runtime.GOOS, GOARCH: runtime.GOARCH, XToolsVersion: "unknown"}
	if req.Build.GOOS != nil && *req.Build.GOOS != "" {
		tc.GOOS = *req.Build.GOOS
	}
	if req.Build.GOARCH != nil && *req.Build.GOARCH != "" {
		tc.GOARCH = *req.Build.GOARCH
	}
	if bi, ok := debug.ReadBuildInfo(); ok {
		for _, d := range bi.Deps {
			if d.Path == "golang.org/x/tools" {
				tc.XToolsVersion = d.Version
			}
		}
	}
	return tc
}

// peakRSSKB reads the process high-water mark on Linux; nil elsewhere.
func peakRSSKB() *int64 {
	data, err := os.ReadFile("/proc/self/status")
	if err != nil {
		return nil
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "VmHWM:") {
			var kb int64
			if _, err := fmt.Sscanf(strings.TrimSpace(strings.TrimPrefix(line, "VmHWM:")), "%d", &kb); err == nil {
				return &kb
			}
		}
	}
	return nil
}
