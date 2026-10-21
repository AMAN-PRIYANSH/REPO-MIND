"""D1 and D4 dataset construction (CP3 deliverable 5).

D1 (Mode 1): 150 advisories, REVIEWED, with core symbols and a GitHub fix commit,
stratified by `created` year with a fixed seed, forcing in every advisory created after the
contamination-control cutoff (docs/evaluation/DATASET_STRATEGY.md, EVALUATION_PLAN.md).

D4 (Mode 2): 120 advisories from the same eligible pool (plus a usable vulnerable_at/
fixed_in pair, which D1 does not need since Mode 1 uses the fix commit directly), explored
until at least 25 have more than 100 candidates or the pool is exhausted.
"""

import random
import subprocess
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import release_range, vulndb
from vulntrace.dataset.report import ReportError, parse_report_file

STDLIB_MODULES = {"std", "cmd"}
CONTAMINATION_CUTOFF = "2026-06-30"  # placeholder until a model is chosen (CP5; CP3.md task spec)

D1_TARGET = 150
D4_TARGET = 120
D4_LARGE_TARGET = 25
D4_LARGE_THRESHOLD = 100


def load_all_cases(cache_dir: Path | None = None, vulndb_commit: str | None = None) -> tuple[list[dict], int]:
    """(cases, parse_error_count). A malformed report is counted, never silently dropped."""
    commit = vulndb_commit or vulndb.pinned_commit()
    reports_dir = vulndb.reports_dir(cache_dir)
    cases, errors = [], 0
    for p in vulndb.iter_report_paths(cache_dir):
        try:
            cases.append(parse_report_file(p, commit, reports_dir))
        except ReportError:
            errors += 1
    return cases, errors


def has_core_symbols(case: dict[str, Any]) -> bool:
    return any(pkg["core_symbols"] for m in case["modules"] for pkg in m["packages"])


def is_stdlib_or_toolchain(case: dict[str, Any]) -> bool:
    return any(m["module"] in STDLIB_MODULES for m in case["modules"])


def eligible_for_d1(case: dict[str, Any]) -> bool:
    """REVIEWED, not withdrawn, not the Go standard library or toolchain ("std"/"cmd" -
    vulndb's own markers for them), at least one core symbol, at least one GitHub fix
    commit."""
    return (case["review_status"] == "REVIEWED" and not case["withdrawn"] and not is_stdlib_or_toolchain(case)
           and has_core_symbols(case) and bool(case["fix_commits"]))


def pick_d4_module(case: dict[str, Any]) -> dict[str, Any] | None:
    """The module to use for a release range: the first with both a vulnerable_at and a
    fixed_in (D1 eligibility does not require this pair at all - Mode 1 uses the fix commit
    diff directly), preferring one that also has core symbols."""
    usable = [m for m in case["modules"] if m["vulnerable_at"] and m["fixed_in"]]
    with_symbols = [m for m in usable if any(pkg["core_symbols"] for pkg in m["packages"])]
    pool = with_symbols or usable
    return pool[0] if pool else None


def eligible_for_d4(case: dict[str, Any]) -> bool:
    return eligible_for_d1(case) and pick_d4_module(case) is not None


def _created_year(case: dict[str, Any]) -> str:
    return (case["created"] or "")[:4] or "UNKNOWN"


def stratified_sample(cases: list[dict[str, Any]], target: int, seed: int,
                      cutoff: str = CONTAMINATION_CUTOFF) -> list[dict[str, Any]]:
    """Every case created after `cutoff` is force-included (contamination control:
    EVALUATION_PLAN.md); the rest are drawn from the remaining pool, stratified by `created`
    year with proportional (largest-remainder) allocation, up to `target` cases total.
    Deterministic for a given `seed`. If the forced set alone reaches or exceeds `target`,
    every forced case is still returned (the forced rule is never capped away)."""
    rng = random.Random(seed)
    forced = [c for c in cases if (c["created"] or "") > cutoff]
    forced_ids = {c["id"] for c in forced}
    pool = [c for c in cases if c["id"] not in forced_ids]
    remaining = target - len(forced)
    if remaining <= 0:
        return sorted(forced, key=lambda c: c["id"])
    if len(pool) <= remaining:
        return sorted(forced + pool, key=lambda c: c["id"])

    by_year: dict[str, list[dict]] = {}
    for c in pool:
        by_year.setdefault(_created_year(c), []).append(c)
    years = sorted(by_year)
    total = len(pool)
    raw = {y: remaining * len(by_year[y]) / total for y in years}
    alloc = {y: int(raw[y]) for y in years}
    shortfall = remaining - sum(alloc.values())
    for y in sorted(years, key=lambda y: raw[y] - alloc[y], reverse=True)[:shortfall]:
        alloc[y] += 1

    selected = []
    for y in years:
        pool_y = sorted(by_year[y], key=lambda c: c["id"])
        rng.shuffle(pool_y)
        selected.extend(pool_y[: alloc[y]])
    return sorted(forced + selected, key=lambda c: c["id"])


def build_d1_case_list(cases: list[dict[str, Any]], seed: int, target: int = D1_TARGET) -> dict[str, Any]:
    eligible = [c for c in cases if eligible_for_d1(c)]
    sample = stratified_sample(eligible, target, seed)
    return {"eligible_count": len(eligible), "sample": sample, "seed": seed, "target": target}


def d4_candidate_count(case: dict[str, Any], module: dict[str, Any], binary, cache_root: Path | None,
                       runner=subprocess.run) -> dict[str, Any]:
    """The ReleaseRange for one D4 candidate case's chosen module."""
    fc = case["fix_commits"][0]
    return release_range.build_release_range(
        case["id"], module["module"], module["vulnerable_at"], module["fixed_in"],
        fc["host"], fc["owner"], fc["repo"], binary=binary, cache_root=cache_root, runner=runner,
    )


def build_d4_case_list(cases: list[dict[str, Any]], seed: int, binary, cache_root: Path | None = None,
                       runner=subprocess.run, target: int = D4_TARGET, large_target: int = D4_LARGE_TARGET,
                       large_threshold: int = D4_LARGE_THRESHOLD, batch_size: int = 60,
                       progress: Callable[[int, int, dict], None] | None = None,
                       cutoff: str = CONTAMINATION_CUTOFF) -> dict[str, Any]:
    """Explore the eligible pool (stratified, same seed/cutoff rule as D1) in batches,
    computing a real ReleaseRange for each, until at least `large_target` cases exceed
    `large_threshold` candidates or the whole pool has been explored. `progress`, if given,
    is called after every case as (explored_so_far, pool_size, release_range_dict) - this
    step is network-bound and can take a long time over the full pool.

    Returns every explored case's ReleaseRange (`explored`, case_id -> dict) plus the final
    D1-style `sample` (forced post-cutoff cases, every large case found, then enough of the
    remaining explored AVAILABLE cases to reach `target`)."""
    eligible = [c for c in cases if eligible_for_d4(c)]
    by_id = {c["id"]: c for c in eligible}
    ordered = stratified_sample(eligible, len(eligible), seed, cutoff)  # a full, seeded, stratified order

    explored: dict[str, dict] = {}
    large_ids: list[str] = []
    i = 0
    while i < len(ordered):
        batch = ordered[i : i + batch_size]
        for case in batch:
            module = pick_d4_module(case)
            rr = d4_candidate_count(case, module, binary, cache_root, runner)
            explored[case["id"]] = rr
            if rr["status"] == "AVAILABLE" and len(rr["candidates"]) > large_threshold:
                large_ids.append(case["id"])
            if progress is not None:
                progress(len(explored), len(ordered), rr)
        i += batch_size
        if len(large_ids) >= large_target and len(explored) >= target:
            break

    forced_ids = {c["id"] for c in eligible if (c["created"] or "") > cutoff}
    final_ids = set(forced_ids) | set(large_ids)
    for case in ordered:  # fill the rest from the explored, seeded, stratified order
        if len(final_ids) >= target:
            break
        if case["id"] in explored:
            final_ids.add(case["id"])

    sample = sorted((by_id[cid] for cid in final_ids), key=lambda c: c["id"])
    return {
        "eligible_count": len(eligible), "explored": explored, "large_ids": sorted(set(large_ids)),
        "sample": sample, "seed": seed, "target": target, "large_target": large_target,
        "pool_exhausted": len(explored) >= len(ordered),
    }
