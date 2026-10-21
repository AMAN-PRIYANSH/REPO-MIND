package main

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"testing"
)

func writeReq(t *testing.T, body string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "req.json")
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func runHelper(t *testing.T, args ...string) (Response, int) {
	t.Helper()
	var out, errb bytes.Buffer
	code := run(args, &out, &errb)
	var resp Response
	if err := json.Unmarshal(out.Bytes(), &resp); err != nil {
		t.Fatalf("stdout is not one JSON object: %v\n%s", err, out.String())
	}
	if bytes.Count(bytes.TrimSpace(out.Bytes()), []byte("\n")) != 0 {
		t.Fatalf("stdout has more than one line: %q", out.String())
	}
	return resp, code
}

func TestRequestErrors(t *testing.T) {
	cases := []struct {
		name, mode, body, code string
	}{
		{"contract major", "reach", `{"contract_version":"2.0","mode":"reach"}`, CodeContractMismatch},
		{"missing version", "reach", `{"mode":"reach"}`, CodeBadRequest},
		{"not json", "reach", `[1,2`, CodeBadRequest},
		{"unknown field", "reach", `{"contract_version":"1.0","mode":"reach","x":1}`, CodeBadRequest},
		{"mode mismatch", "reach", `{"contract_version":"1.0","mode":"funcs","files":["a.go"]}`, CodeBadRequest},
		{"no targets", "reach", `{"contract_version":"1.0","mode":"reach","module_dir":".","main_packages":["./x"]}`, CodeBadRequest},
		{"negative limit", "naive", `{"contract_version":"1.0","mode":"naive","module_dir":".","main_packages":["./x"],"targets":[{"package":"p","symbol":"F"}],"limits":{"max_paths_per_target":-1,"max_path_length":1}}`, CodeBadRequest},
		{"no edges", "edges", `{"contract_version":"1.0","mode":"edges","module_dir":".","main_packages":["./x"]}`, CodeBadRequest},
		{"no files", "funcs", `{"contract_version":"1.0","mode":"funcs"}`, CodeBadRequest},
		{"missing module dir", "reach", `{"contract_version":"1.0","mode":"reach","module_dir":"/nonexistent/vt","main_packages":["./x"],"targets":[{"package":"p","symbol":"F"}]}`, CodeLoadFailed},
	}
	for _, c := range cases {
		resp, code := runHelper(t, c.mode, "--request", writeReq(t, c.body))
		if resp.OK || code != 1 || resp.Error == nil || resp.Error.Code != c.code || resp.ContractVersion != ContractVersion {
			t.Errorf("%s: code=%d resp=%+v err=%+v; want %s", c.name, code, resp, resp.Error, c.code)
		}
	}
}

func TestUsageErrors(t *testing.T) {
	for _, args := range [][]string{{}, {"lift", "--request", "x"}, {"reach"}, {"reach", "--request"}, {"reach", "--request", "/nonexistent/req.json"}} {
		resp, _ := runHelper(t, args...)
		if resp.OK || resp.Error.Code != CodeBadRequest {
			t.Errorf("%v: %+v", args, resp.Error)
		}
	}
}

func TestPanicBecomesInternal(t *testing.T) {
	orig := handlers["funcs"]
	defer func() { handlers["funcs"] = orig }()
	handlers["funcs"] = func(*Request, io.Writer) (any, *Stats, *Error) { panic("boom") }
	resp, code := runHelper(t, "funcs", "--request", writeReq(t, `{"contract_version":"1.0","mode":"funcs","files":["a.go"]}`))
	if resp.OK || code != 1 || resp.Error.Code != CodeInternal || resp.Error.Message != "boom" {
		t.Fatalf("got code=%d %+v", code, resp.Error)
	}
}

func TestFuncsMode(t *testing.T) {
	dir := t.TempDir()
	src := "package q\n\nfunc A() {}\n\ntype L[T any] struct{}\n\nfunc (l *L[T]) Push(v T) {\n}\n\nfunc (S) M() {}\n\ntype S struct{}\n"
	if err := os.WriteFile(filepath.Join(dir, "q.go"), []byte(src), 0o644); err != nil {
		t.Fatal(err)
	}
	body, _ := json.Marshal(map[string]any{"contract_version": "1.0", "mode": "funcs", "module_dir": filepath.ToSlash(dir), "files": []string{"q.go"}})
	resp, code := runHelper(t, "funcs", "--request", writeReq(t, string(body)))
	if !resp.OK || code != 0 {
		t.Fatalf("%+v", resp.Error)
	}
	raw, _ := json.Marshal(resp.Results)
	var files []FileFuncs
	_ = json.Unmarshal(raw, &files)
	want := []FuncInfo{{"A", 3, 3}, {"L.Push", 7, 8}, {"S.M", 10, 10}}
	if len(files) != 1 || files[0].Package != "q" || len(files[0].Functions) != 3 {
		t.Fatalf("%+v", files)
	}
	for i, w := range want {
		if files[0].Functions[i] != w {
			t.Errorf("function %d = %+v; want %+v", i, files[0].Functions[i], w)
		}
	}
	resp, _ = runHelper(t, "funcs", "--request", writeReq(t, `{"contract_version":"1.0","mode":"funcs","files":["/nonexistent/x.go"]}`))
	if resp.OK || resp.Error.Code != CodeLoadFailed {
		t.Fatalf("unreadable file: %+v", resp.Error)
	}
}
