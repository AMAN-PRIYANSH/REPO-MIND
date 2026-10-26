"""Record CP7 verdict outputs for the contract tests (needs Go; run by hand, not by pytest):

    python tests/contract/record_cp7_verdicts.py

Every recording is a real `run_triage` output on the fixture module (or a tiny temporary
module), one per verdict and per reason code. Local absolute paths are replaced by `<local>`.
`index.json` lists the expected verdict and reason codes of each file.
"""

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vulntrace.eval import triage_fixtures as tfx  # noqa: E402
from vulntrace.eval.triage_eval import example_verdict  # noqa: E402
from vulntrace.methods.helper import ensure_helper  # noqa: E402
from vulntrace.paths import FIXTURES_DIR  # noqa: E402
from vulntrace.pipeline import triage  # noqa: E402
from vulntrace.pipeline.cli import default_runners  # noqa: E402

OUT = Path(__file__).resolve().parent / "verdicts_cp7"
CREATED = "2026-10-26T00:00:00Z"
PARSE = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}


def main() -> None:
    binary = ensure_helper()
    base = default_runners(binary=binary)
    OUT.mkdir(exist_ok=True)
    index = {}
    with tempfile.TemporaryDirectory(prefix="vt_cp7_record_") as tmp:
        tmp = Path(tmp)
        pack = tfx.build_pack(tmp / "pack", binary)
        p = pack["Parse"]
        lib_only = tmp / "libonly"
        (lib_only / "lib").mkdir(parents=True)
        (lib_only / "go.mod").write_text("module libonly.example\n\ngo 1.21\n", encoding="utf-8")
        (lib_only / "lib" / "lib.go").write_text("package lib\n\nfunc Parse(s string) string { return s }\n", encoding="utf-8")
        no_mod = tmp / "nomod"
        no_mod.mkdir()

        def corrupting_vta(module_dir, main, targets):
            out = base.vta(module_dir, main, targets)
            for r in out:
                for path in (r["details"].get("paths") or []):
                    for e in path["edges"]:
                        if e["call_site"]["file"]:
                            e["call_site"]["line"] += 1
            return out

        fx = dict(app=FIXTURES_DIR, created_at=CREATED, repo_commit=None)
        new_only = copy.deepcopy(p["fix_evidence"])
        for c in new_only["candidates"]:
            c["side"], c["old_range"] = "NEW", None
        scenarios = {
            "reachable_targets": (dict(case_id="fixture:direct_call", mode="targets", targets=[PARSE], mains=["./cmd/direct_call"], **fx), base),
            "reachable_mode1": (dict(case_id="fixture:direct_call", mode="auto", advisory=p["advisory"], fix_evidence=p["fix_evidence"],
                                     module_rel="", mains=["./cmd/direct_call"], **fx), base),
            "reachable_mode2_candidate_level": (dict(case_id="fixture:direct_call", mode="release", advisory=p["advisory"],
                                                     release_range=p["release_range"], candidate_code=p["candidate_code"],
                                                     module_rel="", mains=["./cmd/direct_call"], **fx), base),
            "not_reachable": (dict(case_id="fixture:safe_only", mode="targets", targets=[PARSE], mains=["./cmd/safe_only"], **fx), base),
            "cd_method_disagreement": (dict(case_id="fixture:present_but_unreachable", mode="targets", targets=[PARSE],
                                            mains=["./cmd/present_but_unreachable"], **fx), base),
            "cd_analysis_failed": (dict(case_id="fixture:direct_call", mode="targets",
                                        targets=[{"package": "vtfixtures/vulnlib", "symbol": "List[T].Push"}],
                                        mains=["./cmd/direct_call"], **fx), base),
            "cd_verifier_rejected": (dict(case_id="fixture:direct_call", mode="targets", targets=[PARSE], mains=["./cmd/direct_call"], **fx),
                                     triage.Runners(vta=corrupting_vta, linker=base.linker, verifier_ctx=base.verifier_ctx)),
            "cd_incomplete_coverage": (dict(case_id="fixture:first-main-only", mode="targets", targets=[PARSE], max_mains=1, **fx), base),
            "cd_mode2_not_reachable_downgraded": (dict(case_id="fixture:interface_not_instantiated", mode="release", advisory=p["advisory"],
                                                       release_range=p["release_range"], candidate_code=p["candidate_code"],
                                                       module_rel="", mains=["./cmd/interface_not_instantiated"], **fx), base),
            "cd_no_fix_evidence": (dict(case_id="fixture:direct_call", mode="fix", advisory=p["advisory"], **fx), base),
            "cd_no_release_evidence": (dict(case_id="fixture:direct_call", mode="release", advisory=p["advisory"], **fx), base),
            "cd_no_target_symbols": (dict(case_id="fixture:direct_call", mode="fix", advisory=p["advisory"], fix_evidence=new_only,
                                          module_rel="", **fx), base),
            "cd_unsupported_target": (dict(case_id="libonly", mode="targets", targets=[{"package": "libonly.example/lib", "symbol": "Parse"}],
                                           app=lib_only, created_at=CREATED), base),
            "cd_app_load_failed": (dict(case_id="nomod", mode="targets", targets=[PARSE], app=no_mod, created_at=CREATED), base),
        }
        for name, (kw, runners) in scenarios.items():
            v = example_verdict(triage.run_triage(triage.TriageRequest(**kw), runners))
            v["timing"] = {k: 0.0 for k in v.get("timing", {})}      # recordings must not churn on timing
            (OUT / f"{name}.json").write_text(json.dumps(v, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            index[name] = {"verdict": v["verdict"], "reason_codes": v["reason_codes"], "mode": v["mode"]}
            print(f"{name}: {v['verdict']} {v['reason_codes']}")
    (OUT / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
