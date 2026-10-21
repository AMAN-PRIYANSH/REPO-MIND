"""CP3 deliverable 5 orchestration: build D1 (FixEvidence) and D4 (ReleaseRange), writing
bulky per-case evidence under a (gitignored) data directory and a small, committed case-list
summary under docs/results/datasets/."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import datasets, fix_evidence
from vulntrace.paths import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"
RESULTS_DATASETS_DIR = REPO_ROOT / "docs" / "results" / "datasets"
DEFAULT_SEED = 20261021  # date-derived, fixed; recorded in every case-list file


def _case_summary(case: dict[str, Any], status: str, counts: dict[str, int]) -> dict[str, Any]:
    return {"id": case["id"], "created": case["created"], "review_status": case["review_status"],
           "fix_commit": case["fix_commits"][0] if case["fix_commits"] else None, "status": status, **counts}


def build_d1(cases: list[dict[str, Any]], binary, cache_root: Path | None = None, runner=subprocess.run,
            seed: int = DEFAULT_SEED, target: int = datasets.D1_TARGET, out_dir: Path = DATA_DIR / "fix_evidence",
            progress: Callable[[int, int, dict], None] | None = None) -> dict[str, Any]:
    picked = datasets.build_d1_case_list(cases, seed, target)
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries, status_counts = [], {}
    for i, case in enumerate(picked["sample"], start=1):
        ev = fix_evidence.build_fix_evidence(case["id"], case["fix_commits"], binary=binary, cache_root=cache_root,
                                             runner=runner)
        (out_dir / f"{case['id']}.json").write_text(json.dumps(ev, indent=2, sort_keys=True), encoding="utf-8")
        status_counts[ev["status"]] = status_counts.get(ev["status"], 0) + 1
        summaries.append(_case_summary(case, ev["status"], {
            "candidate_count": len(ev["candidates"]), "fetched_commits": len(ev["commits"]),
            "unfetchable_commits": len(ev["unfetchable_commits"]),
        }))
        if progress is not None:
            progress(i, len(picked["sample"]), ev)
    return {
        "dataset": "D1", "seed": seed, "target": target, "eligible_count": picked["eligible_count"],
        "sample_count": len(picked["sample"]), "status_counts": status_counts, "cases": summaries,
    }


def build_d4(cases: list[dict[str, Any]], binary, cache_root: Path | None = None, runner=subprocess.run,
            seed: int = DEFAULT_SEED, target: int = datasets.D4_TARGET,
            out_dir: Path = DATA_DIR / "release_range",
            progress: Callable[[int, int, dict], None] | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    picked = datasets.build_d4_case_list(cases, seed, binary, cache_root=cache_root, runner=runner, target=target,
                                         progress=progress)
    by_id = {c["id"]: c for c in picked["sample"]}
    summaries, status_counts = [], {}
    for case_id, rr in picked["explored"].items():
        if case_id not in by_id:
            continue
        (out_dir / f"{case_id}.json").write_text(json.dumps(rr, indent=2, sort_keys=True), encoding="utf-8")
        status_counts[rr["status"]] = status_counts.get(rr["status"], 0) + 1
        summaries.append(_case_summary(by_id[case_id], rr["status"], {
            "candidate_count": len(rr["candidates"]), "commit_count": len(rr["commits"]),
            "large": len(rr["candidates"]) > datasets.D4_LARGE_THRESHOLD,
        }))
    summaries.sort(key=lambda s: s["id"])
    return {
        "dataset": "D4", "seed": seed, "target": target, "eligible_count": picked["eligible_count"],
        "explored_count": len(picked["explored"]), "pool_exhausted": picked["pool_exhausted"],
        "large_found": len(picked["large_ids"]), "large_target": datasets.D4_LARGE_TARGET,
        "sample_count": len(picked["sample"]), "status_counts": status_counts, "cases": summaries,
    }


def write_case_list(summary: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
