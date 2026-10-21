import copy
import json

import pytest

from vulntrace.paths import FIXTURES_DIR
from vulntrace.schemas import validate, validation_errors

pytest.importorskip("jsonschema")

EXAMPLE_PRESENT = {
    "schema_version": "1.0",
    "method": "LINKER_PRESENCE",
    "target": {"package": "ctrl/vulnlib", "symbol": "Parse"},
    "main_package": "ctrl/cmd/a_direct",
    "result": "PRESENT",
    "details": {"matched_binary_symbols": ["ctrl/vulnlib.Parse"], "build_flags": ["-gcflags=all=-l"],
                "go_version": "go1.24.7", "goos": "linux", "goarch": "amd64"},
    "error": None,
    "duration_ms": 812,
}


def test_manifest_file_validates():
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    validate("fixture_manifest", manifest)


def test_manifest_has_at_least_12_cases_and_unique_ids():
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in manifest["cases"]]
    assert len(ids) >= 12
    assert len(ids) == len(set(ids))


def test_example_present_result_validates():
    validate("method_result", EXAMPLE_PRESENT)


def test_example_error_result_validates():
    r = copy.deepcopy(EXAMPLE_PRESENT)
    r["result"] = "ERROR"
    r["error"] = {"code": "UNSUPPORTED_SYMBOL_FORM", "message": "generic"}
    validate("method_result", r)


def test_error_result_without_error_object_is_rejected():
    r = copy.deepcopy(EXAMPLE_PRESENT)
    r["result"] = "ERROR"
    assert validation_errors("method_result", r)


def test_non_error_result_with_error_object_is_rejected():
    r = copy.deepcopy(EXAMPLE_PRESENT)
    r["error"] = {"code": "X", "message": "y"}
    assert validation_errors("method_result", r)


def test_linker_method_cannot_return_callgraph_result():
    r = copy.deepcopy(EXAMPLE_PRESENT)
    r["result"] = "PATH_FOUND"
    assert validation_errors("method_result", r)


def test_missing_schema_version_is_rejected():
    r = copy.deepcopy(EXAMPLE_PRESENT)
    del r["schema_version"]
    assert validation_errors("method_result", r)


def test_manifest_with_bad_truth_is_rejected():
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["cases"][0]["truth"] = "EXPLOITABLE"
    assert validation_errors("fixture_manifest", manifest)


def test_manifest_without_rationale_is_rejected():
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    del manifest["cases"][0]["rationale"]
    assert validation_errors("fixture_manifest", manifest)
