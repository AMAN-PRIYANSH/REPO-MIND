import pytest

from vulntrace.dataset.report import ReportError, parse_report
from vulntrace.schemas import validate

VULNDB_COMMIT = "e0bad56276e98711a598adbab976de7cd914013a"
PATH = "data/reports/GO-2026-5504.yaml"


def test_single_module_report_matches_data_model_shape():
    """Small YAML modelled on the data model's own example (not copied from vulndb)."""
    text = """
id: GO-2026-5504
modules:
    - module: example.com/widget
      versions:
        - introduced: 0.60.0
        - fixed: 0.159.2
      vulnerable_at: 0.159.1
      packages:
        - package: example.com/widget/markup
          symbols:
            - hookedRenderer.renderImageDefault
          derived_symbols:
            - converter.Convert
summary: |-
    Widget: a thing is broken
cves:
    - CVE-2026-35166
ghsas:
    - GHSA-mcv8-8m8x-48pg
references:
    - advisory: https://github.com/example/widget/security/advisories/GHSA-mcv8-8m8x-48pg
    - fix: https://github.com/example/widget/commit/479fe6c654937a850b65e74551dc4e857d52898f
source:
    id: GHSA-mcv8-8m8x-48pg
    created: 2026-07-07T00:41:53.734255436-04:00
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["id"] == "GO-2026-5504"
    assert set(case["aliases"]) == {"CVE-2026-35166", "GHSA-mcv8-8m8x-48pg"}
    assert case["review_status"] == "REVIEWED"
    assert case["withdrawn"] is False
    assert case["created"] == "2026-07-07"
    assert case["fix_commits"] == [{"host": "github.com", "owner": "example", "repo": "widget",
                                    "sha": "479fe6c654937a850b65e74551dc4e857d52898f"}]
    assert case["modules"] == [{
        "module": "example.com/widget", "vulnerable_at": "0.159.1", "fixed_in": "0.159.2",
        "packages": [{"package": "example.com/widget/markup",
                     "core_symbols": ["hookedRenderer.renderImageDefault"],
                     "derived_symbols": ["converter.Convert"]}],
    }]


def test_multiple_modules_each_with_their_own_versions_and_packages():
    """Modelled on golang/vulndb's real jwt-go report shape: an old +incompatible v1 module
    and a /v4 fork, each with independent vulnerable_at/fixed and package symbols."""
    text = """
id: GO-2020-0017
modules:
    - module: github.com/dgrijalva/jwt-go
      versions:
        - introduced: 0.0.0-20150717181359-44718f8a89b0
      vulnerable_at: 3.2.0+incompatible
      packages:
        - package: github.com/dgrijalva/jwt-go
          symbols:
            - MapClaims.VerifyAudience
    - module: github.com/dgrijalva/jwt-go/v4
      versions:
        - fixed: 4.0.0-preview1
      vulnerable_at: 4.0.0-20190408202314-32acca36b99f
      packages:
        - package: github.com/dgrijalva/jwt-go/v4
          symbols:
            - MapClaims.VerifyAudience
summary: Authorization bypass
cves:
    - CVE-2020-26160
references:
    - fix: https://github.com/dgrijalva/jwt-go/commit/ec0a89a131e3e8567adcb21254a5cd20a70ea4ab
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert [m["module"] for m in case["modules"]] == ["github.com/dgrijalva/jwt-go", "github.com/dgrijalva/jwt-go/v4"]
    assert case["modules"][0]["vulnerable_at"] == "3.2.0+incompatible"
    # No "fixed" in the first module's versions at all: fixed_in stays null, never guessed.
    assert case["modules"][0]["fixed_in"] is None
    assert case["modules"][1]["fixed_in"] == "4.0.0-preview1"
    # created falls back to nothing (no source.created and no published): null, not invented.
    assert case["created"] is None


def test_pull_request_fix_reference_is_not_counted_as_a_commit():
    text = """
id: GO-2020-0001
modules: []
summary: s
references:
    - fix: https://github.com/example/app/pull/2237
    - fix: https://github.com/example/app/commit/a71af9c144f9579f6dbe945341c1df37aaf09c0d
review_status: UNREVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert [r["kind"] for r in case["fix_references"]] == ["GITHUB_PR", "GITHUB_COMMIT"]
    assert case["fix_commits"] == [{"host": "github.com", "owner": "example", "repo": "app",
                                    "sha": "a71af9c144f9579f6dbe945341c1df37aaf09c0d"}]


def test_non_github_fix_reference_is_other():
    text = """
id: GO-2020-0012
modules: []
summary: s
references:
    - fix: https://go.dev/cl/220357
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["fix_references"] == [{"url": "https://go.dev/cl/220357", "kind": "OTHER"}]
    assert case["fix_commits"] == []


def test_pseudo_version_is_carried_through_unresolved_in_vulncase():
    """VulnCase stores the raw version string; resolving the pseudo-version's commit is the
    release-range step's job (CP3 deliverable 4), not the report reader's."""
    text = """
id: GO-2020-0004
modules:
    - module: example.com/old
      versions:
        - fixed: 0.0.0-20200131131040-063a3fb69896
      vulnerable_at: 0.0.0-20190311151057-c2ebbac481bb
      packages:
        - package: example.com/old
          symbols:
            - ListenAndServe
summary: s
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["modules"][0]["vulnerable_at"] == "0.0.0-20190311151057-c2ebbac481bb"
    assert case["modules"][0]["fixed_in"] == "0.0.0-20200131131040-063a3fb69896"


def test_withdrawn_report():
    text = """
id: GO-2022-0617
modules:
    - module: k8s.io/kubernetes
      vulnerable_at: 1.31.0
summary: WITHDRAWN
withdrawn: "2024-08-21T16:25:56Z"
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["withdrawn"] is True
    # No "versions" at all: fixed_in is null (never guessed), symbols default to empty.
    assert case["modules"][0]["fixed_in"] is None
    assert case["modules"][0]["packages"] == []


def test_needs_review_status_is_accepted():
    """Observed in the real corpus (32 reports) but not documented in DATA_MODEL.md's
    two-value example; recorded as a design deviation in the CP3 report."""
    text = """
id: GO-2025-3414
modules: []
summary: s
review_status: NEEDS_REVIEW
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["review_status"] == "NEEDS_REVIEW"


def test_cve_metadata_id_used_when_no_cves_list():
    text = """
id: GO-2020-0040
modules: []
summary: s
cve_metadata:
    id: CVE-2020-36562
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    validate("vuln_case", case)
    assert case["aliases"] == ["CVE-2020-36562"]


def test_published_date_used_when_no_source_block():
    text = """
id: GO-2020-0040
modules: []
summary: s
published: 2021-04-14T20:04:52Z
review_status: REVIEWED
"""
    case = parse_report(text, PATH, VULNDB_COMMIT)
    assert case["created"] == "2021-04-14"


def test_missing_id_is_a_report_error():
    with pytest.raises(ReportError):
        parse_report("summary: no id here\n", PATH, VULNDB_COMMIT)


def test_empty_report_body_is_a_report_error():
    with pytest.raises(ReportError):
        parse_report("", PATH, VULNDB_COMMIT)


def test_determinism():
    text = "id: GO-2020-0001\nmodules: []\nsummary: s\nreview_status: REVIEWED\n"
    assert parse_report(text, PATH, VULNDB_COMMIT) == parse_report(text, PATH, VULNDB_COMMIT)


def test_details_comes_from_description_and_defaults_to_empty():
    """CP4: `details` (vulndb `description`) is the second half of the Mode 2 query."""
    base = "id: GO-2026-0001\nsummary: s\n"
    with_desc = parse_report(base + "description: |-\n    Long text.\n", PATH, VULNDB_COMMIT)
    without = parse_report(base, PATH, VULNDB_COMMIT)
    validate("vuln_case", with_desc)
    validate("vuln_case", without)
    assert with_desc["details"] == "Long text."
    assert without["details"] == ""
