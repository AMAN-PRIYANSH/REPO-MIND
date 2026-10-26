"""Loading triage inputs: the advisory (VulnCase) and its evidence.

Evidence is read from the files `dataset materialize` writes (`data/fix_evidence/<ID>.json`,
`data/release_range/<ID>.json`, `data/candidate_code/<ID>.json`); triage never fetches anything
itself, so it needs no network. A missing file is not an error here: the pipeline turns it into
CANT_DETERMINE with NO_FIX_EVIDENCE or NO_RELEASE_EVIDENCE. Advisory and commit text are
untrusted data: they are only tokenised for retrieval, never interpreted.
"""

import json
from pathlib import Path
from typing import Any

from vulntrace.paths import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"


class InputError(Exception):
    """Invalid input (exit code 2)."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc


def load_advisory_file(path: Path) -> dict[str, Any]:
    doc = read_json(path)
    if not isinstance(doc, dict) or not doc.get("id"):
        raise InputError(f"{path} is not a VulnCase JSON object with an id")
    doc.setdefault("_source", f"file:{Path(path).name}")
    return doc


def load_advisory_from_vulndb(advisory_id: str, cache_dir: Path | None = None) -> dict[str, Any]:
    """The VulnCase for `advisory_id` from the pinned vulndb snapshot (`dataset fetch` first)."""
    from vulntrace.dataset import vulndb
    from vulntrace.dataset.report import parse_report_file

    if not vulndb.reports_dir(cache_dir).is_dir():
        raise InputError("no vulndb snapshot; run `python -m vulntrace dataset fetch` once (uses the network), "
                         "or pass --advisory-file")
    for p in vulndb.iter_report_paths(cache_dir):
        if p.stem == advisory_id:
            case = parse_report_file(p, vulndb.pinned_commit(), vulndb.reports_dir(cache_dir))
            case["_source"] = "vulndb"
            return case
    raise InputError(f"advisory {advisory_id} is not in the pinned vulndb snapshot")


def load_evidence(case_id: str, data_dir: Path = DATA_DIR) -> dict[str, Any]:
    d = Path(data_dir)
    return {"fix_evidence": read_json(d / "fix_evidence" / f"{case_id}.json"),
            "release_range": read_json(d / "release_range" / f"{case_id}.json"),
            "candidate_code": read_json(d / "candidate_code" / f"{case_id}.json")}


def parse_target(spec: str) -> dict[str, str]:
    """`<package import path>:<symbol>`, for example `vtfixtures/vulnlib:Parse`."""
    pkg, sep, sym = spec.rpartition(":")
    if not sep or not pkg or not sym:
        raise InputError(f"--target {spec!r}: expected <package>:<symbol>")
    return {"package": pkg, "symbol": sym}
