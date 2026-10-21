"""Re-record the helper responses used by the contract tests (needs Go; run by hand).

    python tests/contract/record_responses.py

Writes tests/contract/responses/*.json and index.json. Responses the real helper cannot
produce on demand are written as SYNTHESISED and say so in the index.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vulntrace.methods.helper import default_runner, ensure_helper  # noqa: E402
from vulntrace.paths import FIXTURES_DIR  # noqa: E402

OUT = Path(__file__).resolve().parent / "responses"
PARSE = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}


def req(mode, **kw):
    r = {"contract_version": "1.0", "mode": mode}
    if mode != "funcs":
        r.update(module_dir=FIXTURES_DIR.as_posix(), main_packages=["vtfixtures/cmd/direct_call"],
                 build={"tags": [], "goos": None, "goarch": None},
                 limits={"max_paths_per_target": 3, "max_path_length": 40})
    r.update(kw)
    return r


def main():
    binary = ensure_helper()
    OUT.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vt_contract_"))
    bad_mod = tmp / "typeerr"
    (bad_mod / "cmd" / "app").mkdir(parents=True)
    (bad_mod / "go.mod").write_text("module tm\n\ngo 1.21\n")
    (bad_mod / "cmd" / "app" / "main.go").write_text('package main\n\nfunc main() { var x int = "s"; _ = x }\n')
    recorded = {
        "reach_path_found": ("reach", req("reach", targets=[PARSE])),
        "reach_no_path": ("reach", req("reach", main_packages=["vtfixtures/cmd/dead_code"], targets=[PARSE])),
        "reach_target_errors": ("reach", req("reach", targets=[
            PARSE, {"package": "vtfixtures/vulnlib", "symbol": "Missing"},
            {"package": "vtfixtures/initdep", "symbol": "X"}, {"package": "vtfixtures/vulnlib", "symbol": "a.b.c"}])),
        "naive_no_path": ("naive", req("naive", main_packages=["vtfixtures/cmd/func_value_map"], targets=[PARSE])),
        "edges": ("edges", req("edges", edges=[
            {"caller": "vtfixtures/cmd/direct_call.main", "callee": "vtfixtures/vulnlib.Parse"},
            {"caller": "vtfixtures/cmd/direct_call.main", "callee": "vtfixtures/vulnlib.Safe"}])),
        "funcs": ("funcs", req("funcs", module_dir=FIXTURES_DIR.as_posix(), files=["vulnlib/vulnlib.go"])),
        "error_bad_request": ("reach", {"contract_version": "1.0", "mode": "reach", "unknown_field": 1}),
        "error_contract_mismatch": ("reach", {"contract_version": "2.0", "mode": "reach"}),
        "error_load_failed": ("reach", req("reach", main_packages=["vtfixtures/vulnlib"], targets=[PARSE])),
        "error_type_errors": ("reach", req("reach", module_dir=bad_mod.as_posix(), main_packages=["./cmd/app"],
                                           targets=[PARSE])),
    }
    index = []
    for name, (mode, request) in recorded.items():
        rp = tmp / f"{name}.json"
        rp.write_text(json.dumps(request))
        rc, out, _ = default_runner([str(binary), mode, "--request", str(rp)], 300)
        resp = json.loads(out)
        (OUT / f"{name}.json").write_text(json.dumps(resp, indent=2, sort_keys=True) + "\n")
        index.append({"file": f"{name}.json", "mode": mode, "provenance": "RECORDED", "exit_code": rc})
    synthesised = {
        "error_internal": ("reach", "INTERNAL", "panic: runtime error (synthesised; a real one needs a helper bug)"),
        "error_target_not_found": ("reach", "TARGET_NOT_FOUND",
                                   "response-level form listed in the contract; the helper reports it per target"),
    }
    for name, (mode, code, msg) in synthesised.items():
        resp = {"contract_version": "1.0", "ok": False, "mode": mode, "error": {"code": code, "message": msg}}
        (OUT / f"{name}.json").write_text(json.dumps(resp, indent=2, sort_keys=True) + "\n")
        index.append({"file": f"{name}.json", "mode": mode, "provenance": "SYNTHESISED", "exit_code": 1})
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    shutil.rmtree(tmp)
    print(f"wrote {len(index)} responses to {OUT}")


if __name__ == "__main__":
    main()
