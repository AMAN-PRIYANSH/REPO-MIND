"""Summaries and the generated results document for CP4 (deliverables 6 and 9).

Reads a results directory written by `eval retrieval` (`cases.json` plus `runs/*.json`) and
renders `docs/results/CP4_RETRIEVAL_RESULTS.md`. Every number is computed here from those files.
All configurations are resampled with the same seeded cluster draws per case group, so a
difference between two configurations has a paired cluster-bootstrap interval.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from vulntrace.eval import retrieval_metrics as rm
from vulntrace.retrieval.chunking import VARIANTS

SEED = 20261021
RETRIEVAL_KINDS = ("bm25", "dense", "hybrid", "hybrid+rerank")
BASELINE_ORDER = ("random", "size", "bid", "bid-only")
SIZE_BUCKETS = ("<=10", "11-100", ">100")
DATE_BUCKETS = ("pre", "post", "undated")
EXPECTED_RETRIEVAL = ("bm25", "dense", "hybrid", "hybrid+rerank")


def load_results(results_dir: Path) -> tuple[dict, list[dict]]:
    d = Path(results_dir)
    cases = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((d / "runs").glob("*.json"))]
    ids = [c["id"] for c in cases["cases"]]
    for r in runs:
        if [row["id"] for row in r["rows"]] != ids:
            raise ValueError(f"run {r['config']} / {r['variant']} does not cover the cases in cases.json in order")
    return cases, runs


class Summaries:
    """Metric summaries for every (run, gold kind, group, denominator)."""

    def __init__(self, cases_doc: dict[str, Any], runs: list[dict[str, Any]], seed: int = SEED):
        self.cases = cases_doc["cases"]
        self.runs = runs
        self.rclone = cases_doc.get("rclone_cluster")
        self.seed = seed
        self._resamplers: dict[tuple, tuple[np.ndarray, rm.ClusterResampler]] = {}
        self._mats: dict[tuple, np.ndarray] = {}

    def group_mask(self, group: str) -> np.ndarray:
        c = self.cases
        if group == "all":
            return np.ones(len(c), dtype=bool)
        if group == "no_rclone":
            return np.array([x["cluster_key"] != self.rclone for x in c])
        kind, _, val = group.partition(":")
        field = {"size": "size_bucket", "date": "date_bucket"}[kind]
        return np.array([x[field] == val for x in c])

    def denom_mask(self, denom: str, gold: str = "core") -> np.ndarray:
        if denom == "b":
            return np.ones(len(self.cases), dtype=bool)
        key = "n_gold_core" if gold == "core" else "n_gold_core_derived"
        return np.array([x[key] > 0 for x in self.cases])

    def _resampler(self, group: str, denom: str, gold: str):
        k = (group, denom, gold)
        if k not in self._resamplers:
            mask = self.group_mask(group) & self.denom_mask(denom, gold)
            clusters = [x["cluster_key"] for x, m in zip(self.cases, mask) if m]
            self._resamplers[k] = (mask, rm.ClusterResampler(clusters, seed=self.seed))
        return self._resamplers[k]

    def matrix(self, run_index: int, gold: str = "core") -> np.ndarray:
        k = (run_index, gold)
        if k not in self._mats:
            run = self.runs[run_index]
            ngold_key = "n_gold_core" if gold == "core" else "n_gold_core_derived"
            self._mats[k] = rm.metric_matrix([row[gold] for row in run["rows"]], [c[ngold_key] for c in self.cases])
        return self._mats[k]

    def summary(self, run_index: int, group: str = "all", denom: str = "b", gold: str = "core") -> dict[str, dict]:
        mask, rs = self._resampler(group, denom, gold)
        vals = self.matrix(run_index, gold)[mask]
        if not len(vals):
            return {m: {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "n": 0,
                        "n_clusters": 0} for m in rm.METRICS}
        return dict(zip(rm.METRICS, rs.summarize(vals)))

    def paired_diff(self, a: int, b: int, metric: str, group: str = "all", denom: str = "b",
                    gold: str = "core") -> dict[str, float]:
        mask, rs = self._resampler(group, denom, gold)
        j = rm.METRICS.index(metric)
        va, vb = self.matrix(a, gold)[mask][:, j], self.matrix(b, gold)[mask][:, j]
        if not len(va):
            return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "n": 0}
        point = float(va.mean() - vb.mean())
        ra, rb = rs.resample_means(va), rs.resample_means(vb)
        if ra is None:
            return {"mean": point, "ci_low": point, "ci_high": point, "n": int(mask.sum())}
        d = (ra - rb)[:, 0]
        lo, hi = (float(x) for x in np.quantile(d, [0.025, 0.975]))
        return {"mean": point, "ci_low": lo, "ci_high": hi, "n": int(mask.sum())}


def _f(x: float) -> str:
    return "-" if x != x else f"{x:.3f}"  # NaN -> "-"


def _ci(m: dict[str, float]) -> str:
    if m["n"] == 0:
        return "-"
    return f"{_f(m['mean'])} [{_f(m['ci_low'])}, {_f(m['ci_high'])}]"


def _label(run: dict[str, Any]) -> str:
    return run["config"] if run["variant"] == "-" else f"{run['config']} · {run['variant']}"


def _order(runs: list[dict[str, Any]]) -> list[int]:
    def key(i):
        r = runs[i]
        if r["kind"] in BASELINE_ORDER:
            return (0, BASELINE_ORDER.index(r["kind"]), "", "")
        return (1, RETRIEVAL_KINDS.index(r["kind"]), r["config"], r["variant"])

    return sorted(range(len(runs)), key=key)


def _runs_for_variant(runs, variant) -> list[int]:
    return [i for i in _order(runs) if runs[i]["variant"] in ("-", variant)]


def _main_table(s: Summaries, idxs: list[int], group: str, denom: str, gold: str = "core") -> list[str]:
    lines = ["| Config | n (clusters) | R@1 | R@5 | R@10 | R@20 | MRR | nDCG@10 |", "|---|---|---|---|---|---|---|---|"]
    for i in idxs:
        sm = s.summary(i, group, denom, gold)
        n = sm["mrr"]
        lines.append(f"| {_label(s.runs[i])} | {n['n']} ({n['n_clusters']}) | {_f(sm['recall@1']['mean'])} | "
                     f"{_f(sm['recall@5']['mean'])} | {_ci(sm['recall@10'])} | {_f(sm['recall@20']['mean'])} | "
                     f"{_ci(sm['mrr'])} | {_f(sm['ndcg@10']['mean'])} |")
    return lines


def _bucket_table(s: Summaries, idxs: list[int], groups: list[tuple[str, str]]) -> list[str]:
    head = "| Config | " + " | ".join(f"{lab}: R@10 (a) | {lab}: MRR (a) | {lab}: R@10 (b) | {lab}: MRR (b)"
                                      for _, lab in groups) + " |"
    lines = [head, "|---|" + "---|" * (4 * len(groups))]
    for i in idxs:
        cells = []
        for g, _ in groups:
            a, b = s.summary(i, g, "a"), s.summary(i, g, "b")
            cells += [_f(a["recall@10"]["mean"]), _f(a["mrr"]["mean"]), _ci(b["recall@10"]), _ci(b["mrr"])]
        lines.append(f"| {_label(s.runs[i])} | " + " | ".join(cells) + " |")
    return lines


def _group_counts(s: Summaries, groups: list[tuple[str, str]]) -> str:
    parts = []
    for g, lab in groups:
        a = int((s.group_mask(g) & s.denom_mask("a")).sum())
        b = int(s.group_mask(g).sum())
        parts.append(f"{lab}: (a) {a}, (b) {b}")
    return "Cases per bucket - " + "; ".join(parts) + "."


def _find(runs, kind, variant="-", config=None) -> int | None:
    for i, r in enumerate(runs):
        if r["kind"] == kind and r["variant"] == variant and (config is None or r["config"] == config):
            return i
    return None


def _beats(s: Summaries, i: int, ref: int, metric: str, group: str = "all") -> tuple[bool, dict, dict, dict]:
    """(clearly better by the evaluation plan's rule - non-overlapping 95% intervals -, method
    summary, reference summary, paired difference)."""
    a, b = s.summary(i, group, "b")[metric], s.summary(ref, group, "b")[metric]
    return a["ci_low"] > b["ci_high"], a, b, s.paired_diff(i, ref, metric, group)


def headline(s: Summaries) -> list[str]:
    runs = s.runs
    ref = _find(runs, "bid")
    retrieval = [i for i in _order(runs) if runs[i]["kind"] in RETRIEVAL_KINDS]
    present = {runs[i]["kind"] for i in retrieval}
    missing = [k for k in EXPECTED_RETRIEVAL if k not in present]
    lines = []
    if ref is None or not retrieval:
        return ["**No retrieval run is in the results directory yet; nothing can be compared with B-ID.**"]
    clear = []
    for i in retrieval:
        for metric in ("mrr", "recall@10"):
            ok, a, b, d = _beats(s, i, ref, metric)
            if ok:
                clear.append((i, metric, a, b, d))
    best = max(retrieval, key=lambda i: s.summary(i)["mrr"]["mean"])
    bm, bb = s.summary(best)["mrr"], s.summary(ref)["mrr"]
    d = s.paired_diff(best, ref, "mrr")
    if not clear:
        lines.append(f"**No retrieval configuration evaluated here clearly beats B-ID** (commit-message search "
                     f"for the advisory's identifiers, remaining candidates in seeded random order) on MRR or "
                     f"Recall@10 over all {bm['n']} scored D4 cases: by the evaluation plan's rule (non-overlapping "
                     f"95% cluster-bootstrap intervals) no difference is a clear improvement. The best by MRR is "
                     f"`{_label(runs[best])}`: MRR {_ci(bm)} vs B-ID {_ci(bb)}; paired difference "
                     f"{_ci(d)}.")
    else:
        names = sorted({f"`{_label(runs[i])}` ({m})" for i, m, *_ in clear})
        lines.append(f"**Retrieval configurations that clearly beat B-ID** over all {bm['n']} scored D4 cases "
                     f"(non-overlapping 95% cluster-bootstrap intervals): {', '.join(names)}. The best by MRR is "
                     f"`{_label(runs[best])}`: MRR {_ci(bm)} vs B-ID {_ci(bb)}; paired difference {_ci(d)}.")
    large = s.summary(best, "size:>100")["mrr"]
    large_ref = s.summary(ref, "size:>100")["mrr"]
    lines.append("")
    lines.append(f"In the `>100`-candidate bucket, where ranking matters, `{_label(runs[best])}` has MRR "
                 f"{_ci(large)} vs B-ID {_ci(large_ref)} (n={large['n']}, {large['n_clusters']} clusters).")
    if missing:
        lines.append("")
        lines.append(f"**Not run yet:** {', '.join(missing)} configurations need the real embedding/reranker models "
                     "and are produced by `notebooks/cp4_retrieval_colab.ipynb`. Until then this document compares "
                     "only what is listed below; it is not the checkpoint's full answer.")
    return lines


def render_cp4_doc(results_dir: Path, source: str) -> str:
    cases_doc, runs = load_results(results_dir)
    s = Summaries(cases_doc, runs)
    cases = cases_doc["cases"]
    n = len(cases)
    n_a = int(s.denom_mask("a").sum())
    no_cand = sum(1 for c in cases if c["n_candidates"] == 0)
    st = cases_doc["chunk_stats"]
    lines = ["# CP4 results: Mode 2 retrieval on D4", "",
             f"Generated by `python -m vulntrace results render --doc cp4` from `{source}`. Do not edit by hand.", "",
             *headline(s), "",
             "## What retrieval can and cannot do here", "",
             f"Retrieval can only rank the candidates a release range contains. {n - n_a} of {n} D4 cases "
             f"({(n - n_a) / n * 100:.0f}%) have **no** core symbol among their candidates ({no_cand} of them have "
             "no candidates at all), so no ranking can find their gold: they score 0 under denominator (b) and are "
             "excluded from denominator (a). CP3's ceiling investigation found more cases with *some* core symbol "
             "missing (the labelled function existed unchanged in the range); recovering those needs caller/callee "
             "expansion or lifting, which CP4 does not do. For the `<=10` bucket any method, including random "
             "order, is nearly trivial; the `>100` bucket is where ranking matters.", "",
             "## Setup", "",
             f"- Cases: {n} (committed D4 list), {cases_doc['cluster_count']} clusters (identical release ranges), "
             f"{cases_doc['range_count']} indexed ranges. Denominator (a), gold inside the candidate set: {n_a}; "
             f"denominator (b), all scored cases: {n}.",
             f"- Gold: candidates whose symbol is a curated core symbol (name-level match, as in CP3). "
             f"Core ∪ derived reported separately below.",
             f"- Chunks: {st.get('chunks', 0)} (one per candidate, shared by cases with the same range); cap "
             f"{cases_doc['chunk_char_cap']} characters per chunk and {cases_doc['commit_char_cap']} for the commit "
             f"line. Truncated by the chunk cap: " + ", ".join(f"`{v}` {st.get(f'truncated[{v}]', 0)}" for v in VARIANTS)
             + "; commit line cut: " + ", ".join(f"`{v}` {st.get(f'commits_truncated[{v}]', 0)}" for v in VARIANTS[1:])
             + f". Chunks with no body text: {st.get('missing_body', 0)}; with a fixed-side body (function only in "
             f"the fixed version): {st.get('body_side_new', 0)}.",
             f"- Queries: advisory summary + details only. Cases whose query contains an advisory identifier: "
             f"{sum(1 for c in cases if c['query_has_advisory_id'])}. Summary-only queries (the report has no "
             f"`description`): {sum(1 for c in cases if not c.get('query_has_details'))} of {n}. Median query length "
             f"{int(np.median([c['query_chars'] for c in cases]))} characters.",
             f"- B-ID matched a commit in {sum(1 for c in cases if c['bid_matched'])} of {n} cases.",
             "- Intervals: 95% percentile bootstrap over clusters (2000 resamples, seed "
             f"{SEED}); each case group uses the same draws for every configuration, so the paired differences "
             "are meaningful. `R@k` = Recall@k (any gold in the top k).", "",
             "### Run environments", ""]
    seen = set()
    for r in runs:
        env = r.get("environment", {})
        key = json.dumps({k: env.get(k) for k in ("repo_commit", "os", "python", "gpu")}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        configs = [_label(x) for x in runs if json.dumps({k: x.get("environment", {}).get(k) for k in
                                                           ("repo_commit", "os", "python", "gpu")}, sort_keys=True) == key]
        lines.append(f"- repo `{env.get('repo_commit')}`{' (dirty)' if env.get('repo_dirty') else ''}, "
                     f"{env.get('os')}, Python {env.get('python')}, GPU {env.get('gpu') or 'none'} - "
                     f"{len(configs)} run(s)")
    models = {}
    for r in runs:
        for role in ("embedder", "reranker"):
            if role in r.get("models", {}):
                m = r["models"][role]
                models[(role, m["model_id"])] = m
    if models:
        lines += ["", "### Models", "", "| Role | Model | Revision | Details |", "|---|---|---|---|"]
        for (role, mid), m in sorted(models.items()):
            details = ", ".join(f"{k}={m[k]}" for k in ("dim", "max_seq_length", "max_length", "device", "kind")
                                if k in m)
            lines.append(f"| {role} | `{mid}` | `{m.get('revision')}` | {details} |")

    for variant in VARIANTS:
        idxs = _runs_for_variant(runs, variant)
        if not any(runs[i]["variant"] == variant for i in idxs):
            continue
        lines += ["", f"## Chunk variant `{variant}`", "",
                  "Baselines that ignore chunk text (random, size, B-ID) are repeated in every variant's table.", "",
                  f"### All scored cases - denominator (b), n = {n}", "", *_main_table(s, idxs, "all", "b"), "",
                  f"### Gold inside the candidate set - denominator (a), n = {n_a}", "",
                  *_main_table(s, idxs, "all", "a"), "",
                  "### By candidate-set size", "", _group_counts(s, [(f"size:{b}", b) for b in SIZE_BUCKETS]), "",
                  *_bucket_table(s, idxs, [(f"size:{b}", b) for b in SIZE_BUCKETS]), "",
                  "### By advisory date (placeholder cutoff " + cases_doc["cutoff"] + ")", "",
                  _group_counts(s, [(f"date:{b}", b) for b in DATE_BUCKETS]), "",
                  *_bucket_table(s, idxs, [(f"date:{b}", b) for b in DATE_BUCKETS]), "",
                  "### Without the nine-case rclone cluster - denominator (b)", "",
                  *_main_table(s, idxs, "no_rclone", "b"), "",
                  "### Against core ∪ derived symbols - denominator (b)", "",
                  *_main_table(s, idxs, "all", "b", gold="core_derived")]

    ref, rnd = _find(runs, "bid"), _find(runs, "random")
    retrieval = [i for i in _order(runs) if runs[i]["kind"] in RETRIEVAL_KINDS]
    if retrieval and ref is not None:
        lines += ["", "## Paired differences against B-ID and random", "",
                  "Method minus baseline, paired cluster bootstrap, denominator (b). An interval that excludes 0 "
                  "is a difference in the paired analysis; the headline uses the evaluation plan's stricter "
                  "non-overlap rule.", "",
                  "| Config | ΔMRR vs B-ID (all) | ΔR@10 vs B-ID (all) | ΔMRR vs B-ID (>100) | ΔMRR vs random (all) |",
                  "|---|---|---|---|---|"]
        for i in retrieval:
            vs_rand = _ci(s.paired_diff(i, rnd, "mrr")) if rnd is not None else "-"
            lines.append(f"| {_label(runs[i])} | {_ci(s.paired_diff(i, ref, 'mrr'))} | "
                         f"{_ci(s.paired_diff(i, ref, 'recall@10'))} | "
                         f"{_ci(s.paired_diff(i, ref, 'mrr', 'size:>100'))} | {vs_rand} |")

    lines += ["", "## Leakage control: do advisory identifiers in commit messages explain the gains?", "",
              f"Chunks whose commit subjects contain an advisory identifier: {st.get('id_in_commit_subjects', 0)}; "
              f"chunks whose code or doc comment contains one: {st.get('id_in_code', 0)}. The query contains an "
              f"identifier in {sum(1 for c in cases if c['query_has_advisory_id'])} cases, so masking can only change "
              "a lexical match in those; it can still change dense scores slightly everywhere it alters text.", ""]
    pairs = []
    for i in retrieval:
        r = runs[i]
        if r["variant"] != "code+commits":
            continue
        masked = _find(runs, r["kind"], "code+commits_idmasked", r["config"])
        only = _find(runs, r["kind"], "code_only", r["config"])
        pairs.append((i, masked, only))
    if pairs:
        lines += ["| Config | MRR code_only | MRR code+commits | MRR idmasked | Δ commits − idmasked | Δ commits − code_only |",
                  "|---|---|---|---|---|---|"]
        for i, masked, only in pairs:
            m = lambda j: _ci(s.summary(j)["mrr"]) if j is not None else "-"
            dm = _ci(s.paired_diff(i, masked, "mrr")) if masked is not None else "-"
            do = _ci(s.paired_diff(i, only, "mrr")) if only is not None else "-"
            lines.append(f"| {runs[i]['config']} | {m(only)} | {m(i)} | {m(masked)} | {dm} | {do} |")
    else:
        lines.append("(No retrieval configuration was run on both `code+commits` variants.)")

    lines += ["", "## Running time", "", "| Config | Prepare (s) | Rank all cases (s) | Embedding cache |", "|---|---|---|---|"]
    for i in _order(runs):
        r = runs[i]
        cache = r.get("models", {}).get("embedding_cache") or {}
        cache_txt = f"embedded {cache.get('embedded')}, cached {cache.get('cached')}" if cache else "-"
        lines.append(f"| {_label(r)} | {r['timing_seconds']['prepare']} | {r['timing_seconds']['rank_all_cases']} | "
                     f"{cache_txt} |")
    return "\n".join(lines) + "\n"
