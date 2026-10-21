"""Opt-in network smoke tests (CP3 deliverable 8): fetch one real advisory's evidence from
the real network. Skipped by default and never run in CI; set VULNTRACE_NETWORK_TESTS=1 to
run them by hand.
"""

import os
import shutil

import pytest

from vulntrace.dataset.fix_evidence import build_fix_evidence
from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.schemas import validate

pytestmark = [
    pytest.mark.skipif(not os.environ.get("VULNTRACE_NETWORK_TESTS"),
                       reason="SKIPPED: opt-in network test (set VULNTRACE_NETWORK_TESTS=1)"),
    pytest.mark.skipif(shutil.which("go") is None or shutil.which("git") is None,
                       reason="SKIPPED: Go toolchain or git not found on PATH"),
]


@pytest.fixture(scope="module")
def helper():
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


def test_real_fix_commit_fetches_and_extracts_evidence(helper, tmp_path):
    """GO-2020-0017 (jwt-go): MapClaims.VerifyAudience, fixed by a real GitHub commit."""
    fix_commit = {"host": "github.com", "owner": "dgrijalva", "repo": "jwt-go",
                 "sha": "ec0a89a131e3e8567adcb21254a5cd20a70ea4ab"}
    ev = build_fix_evidence("GO-2020-0017", [fix_commit], binary=helper, cache_root=tmp_path / "cache")
    validate("fix_evidence", ev)
    assert ev["status"] == "AVAILABLE"
    assert ev["unfetchable_commits"] == []
    assert ev["commits"] == [{"sha": fix_commit["sha"], "parent_sha": "32acca36b99f04b2b52d117d57bb17e17cbd35a8"}]
    symbols = {c["symbol"] for c in ev["candidates"]}
    assert "MapClaims.VerifyAudience" in symbols
