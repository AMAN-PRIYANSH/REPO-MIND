"""golang/vulndb report reader: one report YAML -> one VulnCase (CP3 deliverable 2).

Validated by running over the whole pinned snapshot (4710 reports): see
tests/unit/test_report.py and the opt-in network-free corpus smoke test.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from vulntrace.dataset.govers import InvalidVersion, smallest_fixed_above

SCHEMA_VERSION = "1.0"

_GH_COMMIT = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/commit/([0-9a-fA-F]{7,40})(?:[/?#].*)?$")
_GH_PR = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/\d+")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ReportError(ValueError):
    pass


def _date_part(timestamp: Any) -> str | None:
    s = str(timestamp) if timestamp is not None else ""
    return s[:10] if _DATE.match(s[:10]) else None


def _aliases(report: dict[str, Any]) -> list[str]:
    out = list(report.get("cves") or []) + list(report.get("ghsas") or [])
    cve_meta_id = (report.get("cve_metadata") or {}).get("id")
    if cve_meta_id and cve_meta_id not in out:
        out.append(cve_meta_id)
    return out


def _classify_fix_url(url: str) -> tuple[str, dict[str, str] | None]:
    """(kind, commit-dict-or-None) for one "fix:" reference URL."""
    m = _GH_COMMIT.match(url)
    if m:
        owner, repo, sha = m.groups()
        return "GITHUB_COMMIT", {"host": "github.com", "owner": owner, "repo": repo.removesuffix(".git"), "sha": sha}
    if _GH_PR.match(url):
        return "GITHUB_PR", None
    return "OTHER", None


def _fix_references_and_commits(report: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    references, commits, seen_commits = [], [], set()
    for ref in report.get("references") or []:
        url = ref.get("fix")
        if url is None:
            continue
        kind, commit = _classify_fix_url(url)
        references.append({"url": url, "kind": kind})
        if commit is not None:
            key = (commit["owner"], commit["repo"], commit["sha"])
            if key not in seen_commits:
                seen_commits.add(key)
                commits.append(commit)
    return references, commits


def _module_fixed_in(vulnerable_at: str | None, versions: list[dict[str, str]]) -> str | None:
    if vulnerable_at is None:
        return None
    fixed_candidates = [v["fixed"] for v in versions if "fixed" in v]
    if not fixed_candidates:
        return None
    try:
        return smallest_fixed_above(vulnerable_at, fixed_candidates)
    except InvalidVersion:
        return None


def _packages(module_entry: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for pkg in module_entry.get("packages") or []:
        out.append({
            "package": pkg["package"],
            "core_symbols": list(pkg.get("symbols") or []),
            "derived_symbols": list(pkg.get("derived_symbols") or []),
        })
    return out


def _modules(report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for m in report.get("modules") or []:
        vulnerable_at = m.get("vulnerable_at")
        versions = m.get("versions") or []
        out.append({
            "module": m["module"],
            "vulnerable_at": vulnerable_at,
            "fixed_in": _module_fixed_in(vulnerable_at, versions),
            "packages": _packages(m),
        })
    return out


def parse_report(text: str, report_path: str, vulndb_commit: str) -> dict[str, Any]:
    """Parse one report YAML's text into a VulnCase dict (schemas/vuln_case.schema.json).

    Raises ReportError if the report lacks the bare minimum (an `id`); every other field is
    optional somewhere in the real corpus and is represented as null/empty rather than
    raising, so a single malformed report cannot stop a whole-corpus build.
    """
    report = yaml.safe_load(text) or {}
    if not isinstance(report, dict) or "id" not in report:
        raise ReportError(f"{report_path}: no top-level \"id\"")
    references, commits = _fix_references_and_commits(report)
    created = _date_part((report.get("source") or {}).get("created")) or _date_part(report.get("published"))
    return {
        "schema_version": SCHEMA_VERSION,
        "id": report["id"],
        "aliases": _aliases(report),
        "summary": str(report.get("summary") or ""),
        "review_status": report.get("review_status") or "UNREVIEWED",
        "withdrawn": "withdrawn" in report,
        "created": created,
        "fix_commits": commits,
        "fix_references": references,
        "modules": _modules(report),
        "source": {"vulndb_commit": vulndb_commit, "report_path": report_path},
    }


def parse_report_file(path: Path, vulndb_commit: str, reports_root: Path) -> dict[str, Any]:
    """Like parse_report, but reads from disk and records a report_path relative to
    `reports_root`'s parent (so it reads "data/reports/GO-....yaml", matching the data model)."""
    text = Path(path).read_text(encoding="utf-8")
    rel = Path(path).resolve().relative_to(Path(reports_root).resolve().parent.parent)
    return parse_report(text, rel.as_posix(), vulndb_commit)
