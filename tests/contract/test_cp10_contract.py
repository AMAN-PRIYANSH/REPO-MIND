"""CP10 contract: real recorded verdicts (tests/contract/record_cp10.py, real helper and linker on
fixtures/reachability) for the target-hygiene rules validate and show what the index says."""

import json
from pathlib import Path

import pytest

from vulntrace.schemas import validation_errors

DIR = Path(__file__).resolve().parent / "cp10" / "verdicts"
INDEX = json.loads((DIR / "index.json").read_text(encoding="utf-8"))


def load(name):
    return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(INDEX))
def test_recording_is_valid_and_matches_index(name):
    v, want = load(name), INDEX[name]
    assert validation_errors("verdict", v) == []
    assert (v["verdict"], v["reason_codes"]) == (want["verdict"], want["reason_codes"])
    assert (v.get("target_policy") or {}).get("stratum") == want["stratum"]
    if want["policy"] == "LEGACY":
        assert "target_policy" not in v and all("extra_reason" not in e for e in v["per_symbol"])


def test_only_context_targets_reachable_rests_on_a_reachable_context_only_target():
    v = load("cd_only_context_targets_reachable")
    ctx = {s["symbol"]: s.get("context_only") for s in v["symbols"]}
    assert ctx == {"Parse": True, "Safe": False}
    by = {e["target"]["symbol"]: e for e in v["per_symbol"]}
    assert by["Parse"]["result"] == "REACHABLE" and by["Parse"]["decides_verdict"] is False
    assert by["Parse"]["extra_reason"] == "CONTEXT_ONLY_EXTRA"
    assert by["Safe"]["result"] == "NOT_REACHABLE" and by["Safe"]["decides_verdict"] is True
    # the same inputs with the legacy targets are REACHABLE: hygiene only weakened it
    assert load("reachable_only_context_legacy")["verdict"] == "REACHABLE"


def test_stratum_s_is_decided_by_curated_symbols_only():
    v = load("not_reachable_stratum_s_extra_reachable")
    by = {(e["target"]["symbol"], e["origin"]): e for e in v["per_symbol"]}
    assert by[("Safe", "VULNDB")]["result"] == "NOT_REACHABLE" and by[("Safe", "VULNDB")]["decides_verdict"] is True
    assert by[("Parse", "FIX_CHANGED")]["result"] == "REACHABLE" and by[("Parse", "FIX_CHANGED")]["decides_verdict"] is False
    assert v["target_policy"]["curated_symbols"] == 1 and v["target_policy"]["extra_targets"] == 1


# --- evidence labels (deliverable 2), real recordings ---------------------------------------------------
EDIR = Path(__file__).resolve().parent / "cp10" / "verdicts_evidence"
RDIR = Path(__file__).resolve().parent / "cp10" / "responses"
EINDEX = json.loads((EDIR / "index.json").read_text(encoding="utf-8"))
ROUTE = "Route shown is an example from the call graph; steps marked unconfirmed may not run in this context."


@pytest.mark.parametrize("name", sorted(k for k in EINDEX if k.startswith("evidence_")))
def test_evidence_recording_is_labelled(name):
    v, want = json.loads((EDIR / f"{name}.json").read_text(encoding="utf-8")), EINDEX[name]
    assert validation_errors("verdict", v) == []
    assert v["verdict"] == want["verdict"]
    assert v["path_evidence"]["evidence_level"] == want["evidence_level"]
    assert v["path_evidence"]["statement"] == ROUTE and ROUTE in v["limitations"]
    for e in v["per_symbol"]:
        if e["result"] == "REACHABLE":
            shown = e["shown_path"]
            dyn = [x for x in shown["edges"] if x["kind"] == "DYNAMIC"]
            assert all(x["confirmed"] is False and x["dynamic_kind"] for x in dyn)
            assert all("confirmed" not in x for x in shown["edges"] if x["kind"] == "STATIC")
            assert e["path_evidence"]["dynamic_steps"] == len(dyn)
            assert e["path_evidence"]["evidence_level"] == ("HAS_DYNAMIC_STEPS" if dyn else "STATIC_PATH")
        else:
            assert "shown_path" not in e


def test_helper_ranking_and_labels_are_additive():
    from vulntrace.pipeline.evidence import strip_cp10_evidence
    from vulntrace.schemas import validation_errors as ve

    ranked = json.loads((RDIR / "reach_rank_label.json").read_text(encoding="utf-8"))
    plain = json.loads((RDIR / "reach_cp9_request.json").read_text(encoding="utf-8"))
    assert ve("helper_response", ranked) == [] and ve("helper_response", plain) == []
    for name in ("reach_rank_label", "reach_cp9_request"):
        assert ve("helper_request", json.loads((RDIR / f"{name}.request.json").read_text(encoding="utf-8"))) == []
    f = ranked["results"][0]["feasibility"]
    assert f["rank_rule"] == "FILTER_PASS_THEN_FEWEST_DYNAMIC_THEN_SHORTEST" and f["ranked_path"]["edges"]
    assert all("dynamic_steps" in ex for ex in f["examined"])
    assert "dynamic_kind" not in json.dumps(plain) and "ranked_path" not in json.dumps(plain)
    assert strip_cp10_evidence(ranked["results"]) == plain["results"]
