"""Re-record the CP5b helper responses (lift, callers, callees) used by the contract tests.

    python tests/contract/record_cp5b_responses.py        # needs Go; run by hand

Writes tests/contract/responses_cp5b/*.json and index.json. Every response is RECORDED from the
real helper; the Python-side codes (TIMEOUT, HELPER_MISSING, BAD_RESPONSE) are tested with fake
runners instead. The older recordings in responses/ are left untouched on purpose.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vulntrace.methods.helper import default_runner, ensure_helper  # noqa: E402
from vulntrace.paths import REPO_ROOT  # noqa: E402

OUT = Path(__file__).resolve().parent / "responses_cp5b"
FIX = (REPO_ROOT / "fixtures" / "lifting").as_posix()
TMP_ALIAS = "/tmp/vt_contract"


def t(pkg, sym):
    return {"package": f"vtlift/{pkg}", "symbol": sym}


def req(mode, module_dir=FIX, **kw):
    r = {"contract_version": "1.0", "mode": mode, "module_dir": module_dir}
    r.update(kw)
    return r


def main():
    binary = ensure_helper()
    OUT.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vt_contract_"))
    broken = tmp / "broken"
    (broken / "good").mkdir(parents=True)
    (broken / "bad").mkdir()
    (broken / "user").mkdir()
    (broken / "go.mod").write_text("module bm\n\ngo 1.21\n")
    (broken / "good" / "good.go").write_text("package good\n\nfunc Exported() int { return helper() }\n\nfunc helper() int { return 1 }\n")
    (broken / "bad" / "bad.go").write_text("package bad\n\nfunc Broken( {\n")
    (broken / "user" / "user.go").write_text('package user\n\nimport "bm/bad"\n\nvar _ = bad.Broken\n')
    nothing = tmp / "nothing"
    nothing.mkdir()
    (nothing / "go.mod").write_text("module nl\n\ngo 1.21\n")
    (nothing / "a.go").write_text("package a\n\nfunc F( {\n")

    seeds = [t("private_helper", "parse"), t("interface_call", "impl.run"), t("func_value", "step"),
             t("diamond", "sink"), t("root_only", "orphan"), t("already_exported", "Parse"),
             t("generic_seed", "Map"), t("private_helper", "Nope"), {"package": "not/there", "symbol": "X"}]
    recorded = {
        "lift_ok": ("lift", req("lift", targets=seeds)),
        "lift_nearest_only": ("lift", req("lift", targets=[t("diamond", "sink")], lift_rules=["NEAREST"])),
        "lift_depth_limit": ("lift", req("lift", targets=[t("chain", "a")], limits={"max_lift_depth": 2})),
        "lift_package_not_loaded": ("lift", req("lift", module_dir=broken.as_posix(), targets=[
            {"package": "bm/good", "symbol": "helper"}, {"package": "bm/user", "symbol": "X"}])),
        "callers_two_hops": ("callers", req("callers", targets=[t("diamond", "sink"), t("never_called", "dead")],
                                            limits={"max_hops": 2})),
        "callees_one_hop": ("callees", req("callees", targets=[t("diamond", "Top"), t("interface_call", "Do")])),
        "callees_truncated": ("callees", req("callees", targets=[t("diamond", "Top")], limits={"max_results": 1})),
        "callers_not_in_program": ("callers", req("callers", targets=[{"package": "not/there", "symbol": "X"}])),
        "error_lift_load_failed_dir": ("lift", req("lift", module_dir="/nonexistent/vt", targets=[t("diamond", "sink")])),
        "error_lift_load_failed_nothing_loads": ("lift", req("lift", module_dir=nothing.as_posix(),
                                                             targets=[{"package": "nl", "symbol": "F"}])),
        "error_callers_load_failed_dir": ("callers", req("callers", module_dir="/nonexistent/vt", targets=[t("diamond", "sink")])),
        "error_lift_bad_request": ("lift", req("lift", targets=[t("diamond", "sink")], lift_rules=["SOME"])),
        "error_lift_contract_mismatch": ("lift", {"contract_version": "2.0", "mode": "lift"}),
    }
    index = []
    for name, (mode, request) in recorded.items():
        rp = tmp / f"{name}.json"
        rp.write_text(json.dumps(request))
        rc, out, _ = default_runner([str(binary), mode, "--request", str(rp)], 300)
        text = out.replace(tmp.as_posix(), TMP_ALIAS)
        resp = json.loads(text)
        resp.get("stats", {}).update(duration_ms=0, peak_rss_kb=None)
        (OUT / f"{name}.json").write_text(json.dumps(resp, indent=2, sort_keys=True) + "\n")
        index.append({"file": f"{name}.json", "mode": mode, "provenance": "RECORDED", "exit_code": rc})
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    shutil.rmtree(tmp)
    print(f"wrote {len(index)} responses to {OUT}")


if __name__ == "__main__":
    main()
