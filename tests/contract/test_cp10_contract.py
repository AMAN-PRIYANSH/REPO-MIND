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
