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
from vulntrace.paths import FIXTURES_DIR as FX  # noqa: E402
from vulntrace.pipeline import symbols as sy  # noqa: E402
from vulntrace.pipeline import triage  # noqa: E402
from vulntrace.pipeline.cli import default_runners  # noqa: E402

OUT = Path(__file__).resolve().parent / "cp10"
CREATED = "2026-11-26T00:00:00Z"
FEAS = {"max_examined_paths": 20}
FILE = "vulnlib/vulnlib.go"


def sanitise(obj):
    return json.loads(json.dumps(obj).replace(FX.resolve().as_posix(), "<local>"))


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
    runners = default_runners(binary=binary, feasibility=FEAS)
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


def main() -> None:
    binary = ensure_helper()
    print(json.dumps(record_verdicts(binary), indent=1))


if __name__ == "__main__":
    main()
