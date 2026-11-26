"""Record CP10 verdicts for the contract tests (needs Go; run by hand, not by pytest):

    python tests/contract/record_cp10.py

Every recording is a real `run_triage` output (real helper, real `go build` + `go tool nm`, real
verifier) on the CP2 fixture module `fixtures/reachability` (module `vtfixtures`). The FixEvidence
is written here by hand: two changed functions of `vulnlib/vulnlib.go`, `Parse` (lines 11-21) and
`Safe` (line 31), with one hunk each. In the "context" variant the hunk next to `Parse` changes
only line 23 (a comment line outside its range), so `Parse` is a changed function only through
git's context lines (`context_only`). The advisory is synthetic (`GO-CP10-FIXTURE`), with or
without a curated symbol, so both strata of the CP10 target-hygiene rules run. Local absolute
paths are replaced by `<local>`. `index.json` lists what each file must show.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vulntrace.eval.triage_eval import example_verdict  # noqa: E402
from vulntrace.methods.helper import ensure_helper  # noqa: E402
from vulntrace.methods.callgraph import build_request  # noqa: E402
from vulntrace.methods.helper import default_runner  # noqa: E402
from vulntrace.paths import FEASIBILITY_FIXTURES_DIR as FFX  # noqa: E402
from vulntrace.paths import FIXTURES_DIR as FX  # noqa: E402
from vulntrace.pipeline import symbols as sy  # noqa: E402
from vulntrace.pipeline import triage  # noqa: E402
from vulntrace.pipeline.cli import default_runners  # noqa: E402

OUT = Path(__file__).resolve().parent / "cp10"
CREATED = "2026-11-26T00:00:00Z"
FEAS = {"max_examined_paths": 20}
FILE = "vulnlib/vulnlib.go"


def sanitise(obj):
    text = json.dumps(obj).replace(FX.resolve().as_posix(), "<local>").replace(FFX.resolve().as_posix(), "<local>")
    return json.loads(text)


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def fix_evidence(parse_context_only: bool) -> dict:
    # context variant: three context lines 19-21 (inside Parse), the changed line is 22 (outside it)
    h1 = ({"old_start": 19, "text": " a\n a\n a\n-b\n+c"} if parse_context_only else
          {"old_start": 12, "text": " a\n-b\n+c\n d"})
    hunks = [{"hunk_id": "h1", "file": FILE, "old_start": h1["old_start"], "old_lines": 3, "new_start": h1["old_start"],
              "new_lines": 3, "text": h1["text"]},
             {"hunk_id": "h2", "file": FILE, "old_start": 30, "old_lines": 3, "new_start": 30, "new_lines": 3,
              "text": " a\n-b\n+c\n d"}]
    cands = [{"candidate_id": "c1", "package_dir": "vulnlib", "symbol": "Parse", "side": "BOTH",
              "old_range": {"file": FILE, "start": 11, "end": 21}, "new_range": {"file": FILE, "start": 11, "end": 21},
              "hunk_ids": ["h1"]},
             {"candidate_id": "c2", "package_dir": "vulnlib", "symbol": "Safe", "side": "BOTH",
              "old_range": {"file": FILE, "start": 31, "end": 31}, "new_range": {"file": FILE, "start": 31, "end": 31},
              "hunk_ids": ["h2"]}]
    return {"schema_version": "1.0", "case_id": "GO-CP10-FIXTURE", "status": "AVAILABLE", "commits": [],
            "candidates": cands, "hunks": hunks, "unfetchable_commits": [], "non_go_files_changed": [],
            "test_files_changed": 0}


def advisory(curated: list[str]) -> dict:
    return {"id": "GO-CP10-FIXTURE", "summary": "vtfixtures: synthetic advisory for the CP10 recordings", "details": "",
            "module": "vtfixtures", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
            "fix_commits": [{"host": "local", "owner": "vtfixtures", "repo": "vtfixtures", "sha": "0" * 40}],
            "modules": [{"module": "vtfixtures", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
                         "packages": [{"package": "vtfixtures/vulnlib", "core_symbols": list(curated),
                                       "derived_symbols": []}] if curated else []}]}


# name: (main, context_only?, curated symbols, policy, verdict, reason codes, stratum)
SCENARIOS = {
    "cd_only_context_targets_reachable": ("direct_call", True, [], sy.POLICY_HYGIENE, "CANT_DETERMINE",
                                          ["ONLY_CONTEXT_TARGETS_REACHABLE"], "N"),
    "reachable_only_context_legacy": ("direct_call", True, [], sy.POLICY_LEGACY, "REACHABLE", [], None),
    "reachable_stratum_n": ("direct_call", False, [], sy.POLICY_HYGIENE, "REACHABLE", [], "N"),
    "not_reachable_stratum_s_extra_reachable": ("direct_call", False, ["Safe"], sy.POLICY_HYGIENE, "NOT_REACHABLE", [], "S"),
    "reachable_stratum_s": ("direct_call", False, ["Parse"], sy.POLICY_HYGIENE, "REACHABLE", [], "S"),
}


def record_verdicts(binary) -> dict:
    runners = default_runners(binary=binary, feasibility=FEAS, evidence=True)
    index = {}
    for name, (main, ctx, curated, policy, verdict, reasons, stratum) in SCENARIOS.items():
        req = triage.TriageRequest(case_id=f"cp10:{name}", app=FX, mode="fix", advisory=advisory(curated),
                                   fix_evidence=fix_evidence(ctx), module_rel="", mains=[f"vtfixtures/cmd/{main}"],
                                   max_mains=1, created_at=CREATED, repo_commit=None, target_policy=policy)
        v = triage.run_triage(req, runners)
        v["timing"] = {}
        v = example_verdict(sanitise(v))
        assert (v["verdict"], v["reason_codes"]) == (verdict, reasons), (name, v["verdict"], v["reason_codes"])
        assert (v.get("target_policy") or {}).get("stratum") == stratum, (name, v.get("target_policy"))
        write(OUT / "verdicts" / f"{name}.json", v)
        index[name] = {"main": main, "parse_context_only": ctx, "curated": curated, "policy": policy,
                       "verdict": verdict, "reason_codes": reasons, "stratum": stratum}
    write(OUT / "verdicts" / "index.json", index)
    return index


PARSE_FEAS = {"package": "vtfeas/vulnlib", "symbol": "Parse"}
PARSE_FX = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}
# evidence recordings: name -> (app, main package, target, filter on?, verdict, evidence level)
EVIDENCE = {
    "evidence_dynamic_route": (FFX, "vtfeas/cmd/f1_iface_both", PARSE_FEAS, True, "REACHABLE", "HAS_DYNAMIC_STEPS"),
    "evidence_filter_off": (FFX, "vtfeas/cmd/f1_iface_both", PARSE_FEAS, False, "REACHABLE", "HAS_DYNAMIC_STEPS"),
    "evidence_static_route": (FX, "vtfixtures/cmd/direct_call", PARSE_FX, True, "REACHABLE", "STATIC_PATH"),
    "evidence_not_reachable": (FX, "vtfixtures/cmd/dead_code", PARSE_FX, True, "NOT_REACHABLE", "NO_ROUTE_SHOWN"),
}


def record_evidence(binary) -> dict:
    index = {}
    for name, (app, main, target, filt, verdict, level) in EVIDENCE.items():
        runners = default_runners(binary=binary, feasibility=FEAS if filt else None, evidence=True)
        req = triage.TriageRequest(case_id=f"cp10:{name}", app=app, mode="targets", targets=[target],
                                   mains=[main], max_mains=1, created_at=CREATED, repo_commit=None)
        v = triage.run_triage(req, runners)
        v["timing"] = {}
        v = example_verdict(sanitise(v))
        got = v["path_evidence"]["evidence_level"]
        assert (v["verdict"], got) == (verdict, level), (name, v["verdict"], got)
        write(OUT / "verdicts_evidence" / f"{name}.json", v)
        index[name] = {"main": main, "filter": filt, "verdict": verdict, "evidence_level": got,
                       "dynamic_steps": v["path_evidence"]["dynamic_steps"]}
    # one raw helper response with the CP10 options, and the same request without them
    import tempfile
    for label, kw in (("reach_rank_label", {"label_dynamic": True, "feasibility": {**FEAS, "rank_evidence": True}}),
                      ("reach_cp9_request", {"feasibility": FEAS})):
        req = build_request("reach", FFX, "vtfeas/cmd/f1_iface_both", [PARSE_FEAS], **kw)
        with tempfile.TemporaryDirectory(prefix="vt_cp10_record_") as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(req), encoding="utf-8")
            rc, out, _ = default_runner([str(binary), "reach", "--request", str(path)], 300)
        resp = sanitise(json.loads(out))
        resp["stats"]["duration_ms"] = 0
        if (resp["stats"] or {}).get("feasibility"):
            resp["stats"]["feasibility"]["duration_ms"] = 0
        resp["stats"]["peak_rss_kb"] = None
        write(OUT / "responses" / f"{label}.request.json", sanitise(req))
        write(OUT / "responses" / f"{label}.json", resp)
        index[label] = {"exit_code": rc}
    write(OUT / "verdicts_evidence" / "index.json", index)
    return index


def main() -> None:
    binary = ensure_helper()
    print(json.dumps(record_verdicts(binary), indent=1))
    print(json.dumps(record_evidence(binary), indent=1))


if __name__ == "__main__":
    main()
