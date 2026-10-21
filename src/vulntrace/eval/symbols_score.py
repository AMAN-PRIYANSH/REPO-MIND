"""E0 (D1) and B-ID (D4) baseline scoring (CP3 deliverable 6): reads the case list and
per-case evidence `dataset build` wrote, scores each case, and reports metrics split by the
contamination-control cutoff."""

import json
from pathlib import Path
from typing import Any

from vulntrace.dataset import baselines, build as dataset_build, datasets, materialize, metrics, release_range
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
                seed: int, cutoff: str, cluster_by_id: dict[str, str] | None = None,
                status_by_id: dict[str, str] | None = None) -> dict[str, Any]:
    cluster_by_id = cluster_by_id or {}
    status_by_id = status_by_id or {}
    rows = []
    for summary in case_list:
        case_id = summary["id"]
        if case_id not in predicted_by_id or case_id not in gold_by_id:
            continue
        predicted = predicted_by_id[case_id]
        gold = gold_by_id[case_id]
        rows.append({
            "id": case_id, "created": summary.get("created"),
            "date_bucket": datasets.date_bucket(summary.get("created"), cutoff),
            "cluster_key": cluster_by_id.get(case_id, case_id), "status": status_by_id.get(case_id),
            "predicted": sorted(predicted), "gold_core": sorted(gold["core"]),
            "core": metrics.per_case_scores(predicted, gold["core"]) if gold["core"] else None,
            "core_derived": metrics.per_case_scores(predicted, gold["core_derived"]) if gold["core_derived"] else None,
        })

    def summ(selected: list[dict], key: str, s: int) -> dict[str, Any]:
        sel = [r for r in selected if r[key] is not None]
        return metrics.summarize_clustered([r[key] for r in sel], [r["cluster_key"] for r in sel], s)

    out = {
        "rows": rows,
        "summary_core": summ(rows, "core", seed),
        "summary_core_derived": summ(rows, "core_derived", seed + 100),
        "cutoff": cutoff,
        "cluster_count": len({r["cluster_key"] for r in rows}),
    }
    for i, bucket in enumerate((datasets.DATE_PRE, datasets.DATE_POST, datasets.DATE_UNDATED)):
        name = {"pre": "pre_cutoff", "post": "post_cutoff", "undated": "undated"}[bucket]
        out[f"summary_core_{name}"] = summ([r for r in rows if r["date_bucket"] == bucket], "core", seed + 200 + 100 * i)
    return out


def score_e0(case_list_path: Path, cases_by_id: dict[str, dict], evidence_dir: Path = dataset_build.DATA_DIR / "fix_evidence",
            seed: int = dataset_build.DEFAULT_SEED, cutoff: str = datasets.CONTAMINATION_CUTOFF) -> dict[str, Any]:
    case_list = _load_case_list(case_list_path)
    ids = [c["id"] for c in case_list["cases"]]
    evidence = _load_evidence(ids, evidence_dir)
    cases = [cases_by_id[i] for i in ids if i in cases_by_id]
    gold = _gold_by_id(cases)
    predicted = {cid: baselines.e0_predict(ev) for cid, ev in evidence.items()}
    clusters = {c["id"]: materialize.d1_cluster_key(c) for c in cases}
    result = _score_rows(case_list["cases"], predicted, gold, seed, cutoff, clusters,
                         {cid: ev["status"] for cid, ev in evidence.items()})
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
    clusters = {c["id"]: datasets.d4_cluster_key(c) or c["id"] for c in cases}
    result = _score_rows(case_list["cases"], predicted, gold, seed, cutoff, clusters,
                         {cid: rr["status"] for cid, rr in evidence.items()})
    # CP3 review finding 3: TRUNCATED ranges were searched over only 500 commits, so B-ID
    # there is a lower bound; finding 1: the nine-case rclone cluster.
    core_rows = [r for r in result["rows"] if r["core"] is not None]
    no_trunc = [r for r in core_rows if r["status"] != release_range.STATUS_TRUNCATED]
    no_rclone = [r for r in core_rows if r["cluster_key"] != datasets.RCLONE_CLUSTER]
    result["summary_core_no_truncated"] = metrics.summarize_clustered(
        [r["core"] for r in no_trunc], [r["cluster_key"] for r in no_trunc], seed + 600)
    result["summary_core_no_rclone"] = metrics.summarize_clustered(
        [r["core"] for r in no_rclone], [r["cluster_key"] for r in no_rclone], seed + 700)

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
