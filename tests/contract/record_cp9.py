"""Record CP9 helper responses and verdicts for the contract tests (needs Go; run by hand, not by
pytest):

    python tests/contract/record_cp9.py

Every recording is a real helper response or a real `run_triage` output on the CP9 fixture module
(fixtures/feasibility). The two "rejected" verdicts are real outputs where the helper response was
corrupted on purpose before the pipeline saw it (a wrong line in the filter's evidence path, a wrong
line in a reported infeasible step), so the verifier must reject them. Local absolute paths are
replaced by `<local>`. `index.json` lists what each file must show.
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vulntrace.eval.triage_eval import example_verdict  # noqa: E402
from vulntrace.methods.callgraph import build_request  # noqa: E402
from vulntrace.methods.helper import default_runner, ensure_helper  # noqa: E402
from vulntrace.paths import FEASIBILITY_FIXTURES_DIR as FX  # noqa: E402
from vulntrace.pipeline import triage  # noqa: E402
from vulntrace.pipeline.cli import default_runners  # noqa: E402

OUT = Path(__file__).resolve().parent / "cp9"
CREATED = "2026-11-17T00:00:00Z"
PARSE = {"package": "vtfeas/vulnlib", "symbol": "Parse"}
FEAS = {"max_examined_paths": 20}


def sanitise(obj):
    text = json.dumps(obj).replace(FX.resolve().as_posix(), "<local>")
    return json.loads(text)


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def run(binary, req) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="vt_cp9_record_") as tmp:
        path = Path(tmp) / "request.json"
        path.write_text(json.dumps(req), encoding="utf-8")
        rc, out, _ = default_runner([str(binary), "reach", "--request", str(path)], 300)
    return rc, out


def record_responses(binary) -> dict:
    index = {}
    scenarios = {
        "reach_feasible": ("f1_iface_both", FEAS, "FEASIBLE"),
        "reach_infeasible": ("f2_const_port", FEAS, "INFEASIBLE"),
        "reach_undecided": ("f1_iface_splice", {"max_examined_paths": 20, "max_states": 2}, "UNDECIDED"),
    }
    for name, (case, feas, status) in scenarios.items():
        req = build_request("reach", FX, f"vtfeas/cmd/{case}", [PARSE], feasibility=feas)
        write(OUT / "responses" / f"{name}.request.json", sanitise(req))
        rc, out = run(binary, req)
        resp = sanitise(json.loads(out))
        write(OUT / "responses" / f"{name}.json", resp)
        index[name] = {"case": case, "status": status, "exit_code": rc}
        got = resp["results"][0]["feasibility"]["status"]
        assert got == status, (name, got)
    # the same request without feasibility: no new fields anywhere
    req = build_request("reach", FX, "vtfeas/cmd/f2_const_port", [PARSE])
    rc, out = run(binary, req)
    write(OUT / "responses" / "reach_no_feasibility.json", sanitise(json.loads(out)))
    index["reach_no_feasibility"] = {"case": "f2_const_port", "status": None, "exit_code": rc}
    write(OUT / "responses" / "index.json", index)
    return index


def corrupt(base_vta, what: str):
    def run(module_dir, main, targets):
        out = base_vta(module_dir, main, targets)
        for r in out:
            f = (r.get("details") or {}).get("feasibility")
            if not f:
                continue
            if what == "evidence" and f.get("evidence_path"):
                for e in f["evidence_path"]["edges"]:
                    if e["call_site"]["file"]:
                        e["call_site"]["line"] += 1
            if what == "step":
                for ex in f["examined"]:
                    if ex.get("first_infeasible"):
                        ex["first_infeasible"]["edge"]["call_site"]["line"] += 1
        return out
    return run


def record_verdicts(binary) -> dict:
    base = default_runners(binary=binary, feasibility=FEAS)
    undecided = default_runners(binary=binary, feasibility={"max_examined_paths": 20, "max_states": 2})
    off = default_runners(binary=binary)
    scenarios = {
        # name: (case, runners, verdict, reason codes, entry reason, filter status, failed check)
        "cd_paths_infeasible": ("f2_const_port", base, "CANT_DETERMINE", ["PATHS_INFEASIBLE"], "PATHS_INFEASIBLE", "INFEASIBLE", None),
        "cd_paths_infeasible_f1": ("f1_iface_splice", base, "CANT_DETERMINE", ["PATHS_INFEASIBLE"], "PATHS_INFEASIBLE", "INFEASIBLE", None),
        "cd_paths_infeasible_f3": ("f3_field_never_set", base, "CANT_DETERMINE", ["PATHS_INFEASIBLE"], "PATHS_INFEASIBLE", "INFEASIBLE", None),
        "reachable_filtered": ("f1_iface_both", base, "REACHABLE", [], None, "FEASIBLE", None),
        "reachable_undecided": ("f1_iface_splice", undecided, "REACHABLE", [], None, "UNDECIDED", None),
        "reachable_filter_off": ("f2_const_port", off, "REACHABLE", [], None, None, None),
        "cd_evidence_rejected": ("f1_iface_both", triage.Runners(**{**base.__dict__, "vta": corrupt(base.vta, "evidence")}),
                                 "CANT_DETERMINE", ["VERIFIER_REJECTED"], "VERIFIER_REJECTED", "FEASIBLE", "FILTERED_PATH"),
        "cd_infeasible_step_rejected": ("f2_const_port", triage.Runners(**{**base.__dict__, "vta": corrupt(base.vta, "step")}),
                                        "CANT_DETERMINE", ["VERIFIER_REJECTED"], "VERIFIER_REJECTED", "INFEASIBLE", "INFEASIBLE_STEP"),
    }
    index = {}
    for name, (case, runners, verdict, reasons, entry_reason, status, failed) in scenarios.items():
        req = triage.TriageRequest(case_id=f"cp9:{case}", app=FX, mode="targets", targets=[PARSE],
                                   mains=[f"vtfeas/cmd/{case}"], max_mains=1, created_at=CREATED, repo_commit=None)
        v = triage.run_triage(req, runners)
        v["timing"] = {}
        v = example_verdict(sanitise(v))
        e = v["per_symbol"][0]
        assert (v["verdict"], v["reason_codes"], e["reason_code"]) == (verdict, reasons, entry_reason), (name, v["verdict"], v["reason_codes"])
        assert ((e.get("feasibility") or {}).get("status")) == status, (name, e.get("feasibility"))
        write(OUT / "verdicts" / f"{name}.json", v)
        index[name] = {"case": case, "verdict": verdict, "reason_codes": reasons, "entry_reason": entry_reason,
                       "filter_status": status, "failed_check": failed, "filter_enabled": runners.feasibility is not None}
    write(OUT / "verdicts" / "index.json", index)
    return index


def main() -> None:
    binary = ensure_helper()
    print(json.dumps(record_responses(binary), indent=1))
    print(json.dumps(record_verdicts(binary), indent=1))


if __name__ == "__main__":
    main()
