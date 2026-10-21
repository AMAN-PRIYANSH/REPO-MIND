"""E0 (D1) and B-ID (D4) baseline scoring (CP3 deliverable 6): reads the case list and
per-case evidence `dataset build` wrote, scores each case, and reports metrics split by the
contamination-control cutoff."""

import json
from pathlib import Path
from typing import Any

from vulntrace.dataset import baselines, build as dataset_build, datasets, metrics
from vulntrace.paths import REPO_ROOT

SCHEMA_VERSION = "1.0"


def _load_case_list(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_evidence(ids: list[str], evidence_dir: Path) -> dict[str, dict]:
    out = {}
    for case_id in ids:
        p = evidence_dir / f"{case_id}.json"
        if p.is_file():
            out[case_id] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _gold_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, set]]:
    return {c["id"]: {"core": baselines.core_symbols(c), "core_derived": baselines.core_and_derived_symbols(c)}
           for c in cases}


def _score_rows(case_list: list[dict[str, Any]], predicted_by_id: dict[str, set], gold_by_id: dict[str, dict],
                seed: int, cutoff: str) -> dict[str, Any]:
    rows = []
    for summary in case_list:
        case_id = summary["id"]
        if case_id not in predicted_by_id or case_id not in gold_by_id:
            continue
        predicted = predicted_by_id[case_id]
        gold = gold_by_id[case_id]
        rows.append({
            "id": case_id, "created": summary.get("created"),
            "predicted": sorted(predicted), "gold_core": sorted(gold["core"]),
            "core": metrics.per_case_scores(predicted, gold["core"]) if gold["core"] else None,
            "core_derived": metrics.per_case_scores(predicted, gold["core_derived"]) if gold["core_derived"] else None,
        })
    core_scores = [r["core"] for r in rows if r["core"] is not None]
    core_derived_scores = [r["core_derived"] for r in rows if r["core_derived"] is not None]
    pre = [r["core"] for r in rows if r["core"] is not None and (r["created"] or "") <= cutoff]
    post = [r["core"] for r in rows if r["core"] is not None and (r["created"] or "") > cutoff]
    return {
        "rows": rows,
        "summary_core": metrics.summarize(core_scores, seed),
        "summary_core_derived": metrics.summarize(core_derived_scores, seed + 100),
        "summary_core_pre_cutoff": metrics.summarize(pre, seed + 200),
        "summary_core_post_cutoff": metrics.summarize(post, seed + 300),
        "cutoff": cutoff,
    }


def score_e0(case_list_path: Path, cases_by_id: dict[str, dict], evidence_dir: Path = dataset_build.DATA_DIR / "fix_evidence",
            seed: int = dataset_build.DEFAULT_SEED, cutoff: str = datasets.CONTAMINATION_CUTOFF) -> dict[str, Any]:
    case_list = _load_case_list(case_list_path)
    ids = [c["id"] for c in case_list["cases"]]
    evidence = _load_evidence(ids, evidence_dir)
    cases = [cases_by_id[i] for i in ids if i in cases_by_id]
    gold = _gold_by_id(cases)
    predicted = {cid: baselines.e0_predict(ev) for cid, ev in evidence.items()}
    result = _score_rows(case_list["cases"], predicted, gold, seed, cutoff)
    return {"schema_version": SCHEMA_VERSION, "strategy": baselines.STRATEGY_E0, "dataset": "D1", "seed": seed,
           "case_count": len(ids), "scored_count": len(result["rows"]), **result}


def score_id_search(case_list_path: Path, cases_by_id: dict[str, dict],
                    evidence_dir: Path = dataset_build.DATA_DIR / "release_range",
                    seed: int = dataset_build.DEFAULT_SEED, cutoff: str = datasets.CONTAMINATION_CUTOFF,
                    large_threshold: int = datasets.D4_LARGE_THRESHOLD) -> dict[str, Any]:
    case_list = _load_case_list(case_list_path)
    ids = [c["id"] for c in case_list["cases"]]
    evidence = _load_evidence(ids, evidence_dir)
    cases = [cases_by_id[i] for i in ids if i in cases_by_id]
    gold = _gold_by_id(cases)
    cases_this = {c["id"]: c for c in cases}
    predicted = {cid: baselines.bid_predict(cases_this[cid], rr) for cid, rr in evidence.items() if cid in cases_this}
    result = _score_rows(case_list["cases"], predicted, gold, seed, cutoff)

    sizes = [len(evidence[cid]["candidates"]) for cid in ids if cid in evidence]
    small = sum(1 for n in sizes if n <= 10)
    medium = sum(1 for n in sizes if 11 <= n <= 100)
    large = sum(1 for n in sizes if n > 100)
    gold_outside = sum(1 for cid in ids if cid in evidence and cid in gold
                       and gold[cid]["core"] and not (gold[cid]["core"] & {c["symbol"] for c in evidence[cid]["candidates"]}))
    return {
        "schema_version": SCHEMA_VERSION, "strategy": baselines.STRATEGY_ID_SEARCH, "dataset": "D4", "seed": seed,
        "case_count": len(ids), "scored_count": len(result["rows"]),
        "candidate_set_size": {"n": len(sizes), "small_le_10": small, "medium_11_100": medium,
                               "large": large, "large_threshold": large_threshold},
        "gold_not_in_candidates_count": gold_outside, **result,
    }


def write_score(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "e0" if report["strategy"] == baselines.STRATEGY_E0 else "id_search"
    jp = out_dir / f"{name}_score.json"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return jp, jp
