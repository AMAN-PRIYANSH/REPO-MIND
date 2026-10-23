"""The generated CP5 results document (`docs/results/CP5_LLM_RESULTS.md`, deliverable 10).

Reads the files `eval select` and `eval retrieval --hyde` wrote (a results directory) and
computes every number here, with paired cluster-bootstrap intervals (same seeded draws for every
method on the same cases). The headline numbers use only cases created after the model's
documented training cutoff; if the cutoff is undocumented no case is clean and the headline
uses all cases, flagged "possibly seen". The first paragraph states the main finding, including
a negative one. Wording rule: a method is called better or worse only when the paired 95%
interval excludes 0.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from vulntrace.eval import cp5_stats as st
from vulntrace.eval.retrieval_report import Summaries
from vulntrace.llm.models_config import (BUCKET_POST, BUCKET_POSSIBLY_SEEN, BUCKET_PRE, BUCKET_UNDATED,
                                         contamination_bucket)

SIZE_BUCKETS = (("<=10", 0, 10), ("11-100", 11, 100), (">100", 101, 10**9))
E1_COLS = ("precision0", "recall", "f1", "exact", "any_hit")


def _f(x: float) -> str:
    return "-" if x != x else f"{x:.3f}"


def _ci(m: dict[str, float]) -> str:
    return "-" if not m.get("n") else f"{_f(m['mean'])} [{_f(m['ci_low'])}, {_f(m['ci_high'])}]"


def verdict(d: dict[str, float]) -> str:
    if not d.get("n"):
        return "no data"
    if d["ci_low"] > 0:
        return "better (interval excludes 0)"
    if d["ci_high"] < 0:
        return "worse (interval excludes 0)"
    return "no detectable difference (interval includes 0)"


# --- loading ----------------------------------------------------------------------------------------
def load_dir(results_dir: Path) -> dict[str, Any]:
    d = Path(results_dir)
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, Any] = {"e1": {}, "s1": {}, "hyde": {}}
    for p in sorted(d.glob("select_fix__*.json")):
        doc = load(p)
        out["e1"][doc["model"]["alias"]] = doc
    for p in sorted(d.glob("select_release__*__k*.json")):
        doc = load(p)
        out["s1"][(doc["model"]["alias"], doc["k"])] = doc
    for sub in sorted(d.glob("hyde__*")):
        if (sub / "hyde_meta.json").is_file():
            meta = load(sub / "hyde_meta.json")
            runs = [load(p) for p in sorted((sub / "runs").glob("*.json"))]
            out["hyde"][meta["model"]["alias"]] = {"meta": meta, "cases": load(sub / "cases.json"), "runs": runs}
    return out


def _is_fake(doc_model: dict[str, Any]) -> bool:
    return bool(doc_model.get("dry_run") or doc_model.get("kind") == "FAKE")


# --- groups -----------------------------------------------------------------------------------------
def buckets(rows: list[dict[str, Any]], cutoff: str | None) -> list[str]:
    return [contamination_bucket(r.get("created"), cutoff) for r in rows]


def group_defs(rows, cutoff) -> list[tuple[str, str, list[bool]]]:
    """(key, label, mask): the headline group first, then the others."""
    b = buckets(rows, cutoff)
    n = len(rows)
    mk = lambda f: [f(x) for x in b]
    if cutoff:
        head = ("headline", f"post-cutoff (created after {cutoff[:10]}) - HEADLINE", mk(lambda x: x == BUCKET_POST))
        rest = [("pre", f"pre-cutoff (on or before {cutoff[:10]})", mk(lambda x: x == BUCKET_PRE))]
    else:
        head = ("headline", "all dated cases - cutoff undocumented, every case possibly seen - HEADLINE",
                mk(lambda x: x == BUCKET_POSSIBLY_SEEN))
        rest = []
    rest += [("undated", "undated (no created date)", mk(lambda x: x == BUCKET_UNDATED)), ("all", "all cases", [True] * n)]
    return [head, *rest]


def _sub(rows, mask):
    return [r for r, m in zip(rows, mask) if m]


def _group(rows):
    return st.Group([r["cluster_key"] for r in rows])


def contamination_counts(rows, cutoff) -> str:
    return "; ".join(f"{label.split(' (')[0].split(' -')[0]}: {sum(mask)}" for _k, label, mask in group_defs(rows, cutoff)[:-1]) \
        + f"; total {len(rows)}"


# --- E1 / S1 tables -----------------------------------------------------------------------------------
def _rate(rows, pred) -> str:
    g = _group(rows)
    return _ci(st.rate_ci(g, [pred(r) for r in rows])) if rows else "-"


def _status_rates(rows) -> tuple[str, str, str]:
    return (_rate(rows, lambda r: r["llm"]["status"] == "INVALID"),
            _rate(rows, lambda r: r["llm"]["status"] == "VALID" and r["llm"]["abstain"]),
            _rate(rows, lambda r: r["llm"]["status"] == "NOT_ASKED"))


def _method_row(rows, method, gold, g) -> list[str]:
    ms = [r["m"][method][gold] for r in rows]
    s = g.summary(st.matrix(ms))
    p_ans, n_ans = st.answered_precision(ms)
    cols = dict(zip(st.COLUMNS, s))
    return [f"{_f(p_ans)} (n={n_ans})", _ci(cols["recall"]), _ci(cols["f1"]), _ci(cols["exact"]), _ci(cols["any_hit"])]


def _paired_cells(rows, a, b, gold, g) -> list[str]:
    d = dict(zip(st.COLUMNS, g.paired(st.matrix([r["m"][a][gold] for r in rows]), st.matrix([r["m"][b][gold] for r in rows]))))
    return [_ci(d[c]) for c in ("precision0", "recall", "f1", "exact", "any_hit")]


def e1_section(alias: str, doc: dict[str, Any]) -> list[str]:
    rows, cutoff = doc["rows"], doc["model"]["cutoff"]
    out = [f"## E1 (Mode 1, D1): `{alias}` vs E0", "",
           f"The model chooses from the functions the fix commit changed (at most {doc['max_selected']}), seeing the advisory "
           "text and the numbered non-test hunks. E0 predicts every changed function. A case whose evidence has no candidate "
           "functions is not asked: both methods predict nothing. An INVALID or ERROR answer predicts nothing (a miss, never "
           "dropped).", "",
           f"Contamination split ({doc['model']['cutoff_source'][:160]}...): {contamination_counts(rows, cutoff)}.", ""]
    c = doc["counts"]
    out += [f"Run: {c['asked']} cases asked ({c['not_asked']} had no candidates), {c['valid']} valid, {c['invalid']} INVALID, "
            f"{c['error']} server errors, {c['abstain']} abstained, {c['retried']} needed the retry; "
            f"{c['input_tokens']} prompt / {c['output_tokens']} completion tokens, {c['llm_seconds']} s of LLM time over "
            f"{c['calls']} calls ({c['cached_calls']} served from cache). Largest prompt: {c.get('max_input_tokens', 0)} tokens "
            "(the Colab notebook configures a 32768-token context; a value near it would mean the server may have cut the prompt).", ""]
    trunc = [r["id"] for r in rows if r["prompt_meta"].get("diff_truncated")]
    out += [f"Diff truncation rule: each hunk cut at 2500 characters, hunks added in order until 20000 characters are used, "
            f"the rest omitted (candidates are never cut). Cases with a truncated diff: {len(trunc)}"
            + (f" ({', '.join(trunc[:30])}{', ...' if len(trunc) > 30 else ''})" if trunc else "") + ".", ""]
    for gold, gold_label in (("core", "core symbols"), ("core_derived", "core ∪ derived symbols")):
        out += [f"### Against {gold_label}", ""]
        for key, label, mask in group_defs(rows, cutoff):
            sub = _sub(rows, mask)
            if not sub:
                out += [f"**{label}**: no cases.", ""]
                continue
            g = _group(sub)
            inv, ab, na = _status_rates(sub)
            out += [f"**{label}** - n = {len(sub)} ({g.n_clusters} clusters)", "",
                    "| Method | precision (answered) | recall | F1 | exact match | any-hit | abstain rate | invalid rate |",
                    "|---|---|---|---|---|---|---|---|",
                    f"| E0 (all changed functions) | {' | '.join(_method_row(sub, 'e0', gold, g))} | 0 (never abstains) | n/a |",
                    f"| LLM `{alias}` | {' | '.join(_method_row(sub, 'llm', gold, g))} | {ab} (not asked: {na}) | {inv} |", "",
                    "| Paired LLM − E0 | Δ precision (0 if none) | Δ recall | Δ F1 | Δ exact match | Δ any-hit |",
                    "|---|---|---|---|---|---|", f"| {label.split(' (')[0].split(' -')[0]} | {' | '.join(_paired_cells(sub, 'llm', 'e0', gold, g))} |", ""]
    out += ["### By number of changed functions (headline group)", ""]
    head_rows = _sub(rows, group_defs(rows, cutoff)[0][2])
    out += _size_table(head_rows, "n_candidates", "llm", "e0", "core")
    return out


def _size_table(rows, size_key, a, b, gold) -> list[str]:
    out = ["| Candidates | n (clusters) | " + a + " any-hit | " + b + " any-hit | Δ any-hit | Δ F1 |", "|---|---|---|---|---|---|"]
    for name, lo, hi in SIZE_BUCKETS:
        sub = [r for r in rows if lo <= r[size_key] <= hi]
        if not sub:
            out.append(f"| {name} | 0 | - | - | - | - |")
            continue
        g = _group(sub)
        ma, mb = st.matrix([r["m"][a][gold] for r in sub]), st.matrix([r["m"][b][gold] for r in sub])
        d = dict(zip(st.COLUMNS, g.paired(ma, mb)))
        out.append(f"| {name} | {len(sub)} ({g.n_clusters}) | {_ci(dict(zip(st.COLUMNS, g.summary(ma)))['any_hit'])} | "
                   f"{_ci(dict(zip(st.COLUMNS, g.summary(mb)))['any_hit'])} | {_ci(d['any_hit'])} | {_ci(d['f1'])} |")
    return out + [""]


def s1_section(alias: str, k: int, doc: dict[str, Any]) -> list[str]:
    rows, cutoff = doc["rows"], doc["model"]["cutoff"]
    r = doc["retriever"]
    out = [f"## S1 (Mode 2, D4): `{alias}` choosing from the top {k} of `{r['config']}` ({r['variant']}) vs the retriever's top-1", "",
           f"The model sees the advisory text and the {k} best-ranked candidates (ID, signature, commit subjects, doc comment, "
           f"code; code cut at 1500 characters) and picks at most {doc['max_selected']}, or abstains. Baseline: the retriever's "
           "first candidate. Two denominators as in CP4: (a) cases whose gold function is inside the top-k (the only cases where "
           "choosing can matter); (b) all scored cases. A case with no candidates is not asked.", "",
           f"Contamination split: {contamination_counts(rows, cutoff)}.", ""]
    c = doc["counts"]
    out += [f"Run: {c['asked']} asked, {c['valid']} valid, {c['invalid']} INVALID, {c['error']} errors, {c['abstain']} abstained, "
            f"{c['retried']} retried; {c['input_tokens']} / {c['output_tokens']} tokens; {c['llm_seconds']} s LLM time "
            f"({c['cached_calls']}/{c['calls']} calls cached).", ""]
    for gold, gold_label in (("core", "core symbols"), ("core_derived", "core ∪ derived symbols")):
        ink = "gold_in_topk" if gold == "core" else "gold_derived_in_topk"
        out += [f"### Against {gold_label}", ""]
        for key, label, mask in group_defs(rows, cutoff):
            for dn, dlabel, dm in (("b", "(b) all scored cases", [True] * len(rows)), ("a", "(a) gold inside the top-k", [r[ink] for r in rows])):
                sub = _sub(rows, [m and d for m, d in zip(mask, dm)])
                if not sub:
                    out += [f"**{label}, {dlabel}**: no cases.", ""]
                    continue
                g = _group(sub)
                inv, ab, na = _status_rates(sub)
                out += [f"**{label}, {dlabel}** - n = {len(sub)} ({g.n_clusters} clusters)", "",
                        "| Method | any-hit | precision (answered) | abstain rate | invalid rate |", "|---|---|---|---|---|",
                        f"| retriever top-1 | {_method_row(sub, 'top1', gold, g)[4]} | {_method_row(sub, 'top1', gold, g)[0]} | 0 | n/a |",
                        f"| LLM `{alias}` | {_method_row(sub, 'llm', gold, g)[4]} | {_method_row(sub, 'llm', gold, g)[0]} | {ab} | {inv} |", "",
                        "| Paired LLM − top-1 | Δ any-hit | Δ precision (0 if none) | Δ F1 |", "|---|---|---|---|",
                        f"| | {_paired_cells(sub, 'llm', 'top1', gold, g)[4]} | {_paired_cells(sub, 'llm', 'top1', gold, g)[0]} | "
                        f"{_paired_cells(sub, 'llm', 'top1', gold, g)[2]} |", ""]
    out += ["### By candidate-set size (headline group, denominator (b), core)", ""]
    out += _size_table(_sub(rows, group_defs(rows, cutoff)[0][2]), "n_candidates", "llm", "top1", "core")
    return out


# --- HyDE -------------------------------------------------------------------------------------------
def hyde_section(alias: str, h: dict[str, Any]) -> list[str]:
    meta, cases_doc, runs = h["meta"], h["cases"], h["runs"]
    cutoff = meta["model"]["cutoff"]
    created = {r["id"]: r["created"] for r in meta["rows"]}
    facts = []
    for c in cases_doc["cases"]:
        f = dict(c)
        f["date_bucket"] = contamination_bucket(created.get(c["id"]), cutoff)
        facts.append(f)
    cdoc = {**cases_doc, "cases": facts}
    s = Summaries(cdoc, runs)
    cn = meta["counts"]
    out = [f"## HyDE (Mode 2, D4): `{alias}`", "",
           f"For each advisory the model wrote one hypothetical Go function (prompt `{meta['prompt']['version']}`, at most "
           f"{meta['char_cap']} characters); it is used only as a retrieval query. {cn['cases']} generations: {cn['empty']} empty, "
           f"{cn['truncated']} cut at the cap, {cn['errors']} server errors; {cn['input_tokens']} / {cn['output_tokens']} tokens, "
           f"{cn['llm_seconds']} s. Retriever: `{meta['retriever']['config']}` on `{meta['retriever']['variant']}` chunks, secondary row "
           f"`{meta['retriever']['secondary']}`. `query` is the CP4 query unchanged.", ""]
    heads = {"headline": "post-cutoff - HEADLINE" if cutoff else "all dated cases (cutoff undocumented) - HEADLINE"}
    groups = [("date:post" if cutoff else f"date:{BUCKET_POSSIBLY_SEEN}", heads["headline"])]
    if cutoff:
        groups.append(("date:pre", "pre-cutoff"))
    groups += [("date:undated", "undated"), ("all", "all cases")]
    counts = "; ".join(f"{lab.split(' -')[0]}: {int(s.group_mask(g).sum())}" for g, lab in groups)
    out += [f"Cases per group - {counts}.", ""]
    by = {}
    for i, r in enumerate(runs):
        by.setdefault(r["config"], {})[r["hyde"]] = i
    body: list[str] = []
    n_cmp = n_excl = 0
    for group, glabel in groups:
        for dn, dlabel in (("b", "(b) all scored cases"), ("a", "(a) gold inside the candidate set")):
            if not int((s.group_mask(group) & s.denom_mask(dn)).sum()):
                continue
            body += [f"**{glabel}, {dlabel}**", "", "| Retriever | Query | n (clusters) | R@1 | R@10 | MRR | ΔMRR vs query | ΔR@10 vs query | Verdict on MRR |",
                    "|---|---|---|---|---|---|---|---|---|"]
            for cfg, vs in by.items():
                base = vs.get("query")
                for v in ("query", "query+hyde", "hyde-only"):
                    if v not in vs:
                        continue
                    sm = s.summary(vs[v], group, dn)
                    if v == "query" or base is None:
                        dm = dr = "-"
                        ver = "baseline"
                    else:
                        d1, d2 = s.paired_diff(vs[v], base, "mrr", group, dn), s.paired_diff(vs[v], base, "recall@10", group, dn)
                        dm, dr, ver = _ci(d1), _ci(d2), verdict(d1)
                        n_cmp += 1
                        n_excl += int(bool(d1.get("n")) and (d1["ci_low"] > 0 or d1["ci_high"] < 0))
                    body.append(f"| {cfg} | {v} | {sm['mrr']['n']} ({sm['mrr']['n_clusters']}) | {_f(sm['recall@1']['mean'])} | "
                               f"{_ci(sm['recall@10'])} | {_ci(sm['mrr'])} | {dm} | {dr} | {ver} |")
            body.append("")
    out += [f"**How many comparisons this table holds.** `{alias}` has {n_cmp} comparisons against `query` in the tables below "
            f"(retriever x query+hyde / hyde-only x group x denominator), so {n_cmp} intervals on MRR and {n_cmp} on R@10, none "
            f"corrected for multiple comparisons. {n_excl} of the {n_cmp} MRR intervals exclude 0. With that many 95% intervals, "
            f"about {n_cmp * 0.05:.1f} would exclude 0 by chance alone if there were no effect and the comparisons were independent "
            f"(they overlap: same cases and retrievers, so this is a rough guide only). A single borderline interval is not a "
            f"finding; read it only if it is consistent across retrievers, groups and models.", ""]
    out += body
    return out


# --- document -----------------------------------------------------------------------------------------
def _headline_cell(rows, cutoff, a, b, gold="core"):
    mask = group_defs(rows, cutoff)[0][2]
    sub = _sub(rows, mask)
    if not sub:
        return None
    g = _group(sub)
    ma, mb = st.matrix([r["m"][a][gold] for r in sub]), st.matrix([r["m"][b][gold] for r in sub])
    d = dict(zip(st.COLUMNS, g.paired(ma, mb)))
    s = dict(zip(st.COLUMNS, g.summary(ma)))
    sb = dict(zip(st.COLUMNS, g.summary(mb)))
    return len(sub), g.n_clusters, d, s, sb


def main_finding(res: dict[str, Any]) -> list[str]:
    lines = []
    for alias, doc in res["e1"].items():
        cell = _headline_cell(doc["rows"], doc["model"]["cutoff"], "llm", "e0")
        if cell:
            n, nc, d, s, sb = cell
            lines.append(f"- **E1, `{alias}`** ({n} headline cases, {nc} clusters): F1 {_ci(s['f1'])} vs E0 {_ci(sb['f1'])}; "
                         f"paired ΔF1 {_ci(d['f1'])}, Δ any-hit {_ci(d['any_hit'])}, Δ exact match {_ci(d['exact'])}: LLM vs E0 - F1: "
                         f"{verdict(d['f1'])}; any-hit: {verdict(d['any_hit'])}. INVALID rate "
                         f"{_status_rates(_sub(doc['rows'], group_defs(doc['rows'], doc['model']['cutoff'])[0][2]))[0]}.")
        else:
            lines.append(f"- **E1, `{alias}`**: the headline group is empty.")
    for (alias, k), doc in res["s1"].items():
        rows = [r for r in doc["rows"] if r["gold_in_topk"]]
        cell = _headline_cell(rows, doc["model"]["cutoff"], "llm", "top1")
        if cell:
            n, nc, d, s, sb = cell
            lines.append(f"- **S1, `{alias}`, k={k}** (headline cases whose gold is in the top-{k}: {n}, {nc} clusters): any-hit "
                         f"{_ci(s['any_hit'])} vs retriever top-1 {_ci(sb['any_hit'])}; paired Δ {_ci(d['any_hit'])}: LLM vs top-1: "
                         f"{verdict(d['any_hit'])}.")
        else:
            lines.append(f"- **S1, `{alias}`, k={k}**: the headline group (denominator (a)) is empty.")
    for alias, h in res["hyde"].items():
        cutoff = h["meta"]["model"]["cutoff"]
        created = {r["id"]: r["created"] for r in h["meta"]["rows"]}
        facts = [{**c, "date_bucket": contamination_bucket(created.get(c["id"]), cutoff)} for c in h["cases"]["cases"]]
        s = Summaries({**h["cases"], "cases": facts}, h["runs"])
        group = "date:post" if cutoff else f"date:{BUCKET_POSSIBLY_SEEN}"
        main_cfg = h["meta"]["retriever"]["config"]
        idx = {r["hyde"]: i for i, r in enumerate(h["runs"]) if r["config"] == main_cfg}
        if "query" in idx and "query+hyde" in idx and int(s.group_mask(group).sum()):
            d = s.paired_diff(idx["query+hyde"], idx["query"], "mrr", group)
            lines.append(f"- **HyDE, `{alias}`** (`{main_cfg}`, {int(s.group_mask(group).sum())} headline cases): MRR "
                         f"{_ci(s.summary(idx['query'], group)['mrr'])} with the plain query, "
                         f"{_ci(s.summary(idx['query+hyde'], group)['mrr'])} with query+HyDE; paired ΔMRR {_ci(d)}: {verdict(d)}.")
    return lines


def render_cp5_doc(results_dir: Path, source: str) -> str:
    res = load_dir(results_dir)
    fakes_ = [a for a, d in res["e1"].items() if _is_fake(d["model"])] + [a for (a, _k), d in res["s1"].items() if _is_fake(d["model"])] \
        + [a for a, h in res["hyde"].items() if _is_fake(h["meta"]["model"])]
    out = ["# CP5 results: LLM closed-set selection and HyDE", "",
           f"Generated by `python -m vulntrace results render --doc cp5` from `{source}`. Do not edit by hand.", ""]
    if fakes_:
        out += ["> **WARNING: some results come from the FAKE LLM / fake embedder (a dry run).** Their numbers test the pipeline only "
                "and are not results about any language model.", ""]
    if not (res["e1"] or res["s1"] or res["hyde"]):
        return "\n".join(out + ["**No CP5 result files were found; nothing is claimed.**", ""])
    out += ["**Main finding.** The paragraph below states what the language model adds over the baselines it is compared with, "
            "using the headline group of each model (cases created after the model's documented training cutoff; all dated cases, "
            "flagged as possibly seen, when no cutoff is documented). \"Better\" or \"worse\" means the paired 95% cluster-bootstrap "
            "interval excludes 0; anything else is \"no detectable difference\". An LLM that does not help is a valid result.", "",
            *main_finding(res), ""]
    absent = [n for n, v in (("E1 (select --mode fix)", res["e1"]), ("S1 (select --mode release)", res["s1"]),
                             ("HyDE (retrieval --hyde)", res["hyde"])) if not v]
    if absent:
        out += [f"**Not run / not in this directory:** {', '.join(absent)}.", ""]
    models = {}
    for a, d in res["e1"].items():
        models[a] = d["model"]
    for (a, _k), d in res["s1"].items():
        models[a] = d["model"]
    for a, h in res["hyde"].items():
        models[a] = h["meta"]["model"]
    out += ["## Models, prompts, settings", "", "| Alias | Ollama tag | Digest reported by the server | Params / quantization | Documented training cutoff | Source of the cutoff |",
            "|---|---|---|---|---|---|"]
    for a, m in models.items():
        out.append(f"| {a} | `{m['ollama_tag']}` | `{m.get('model_digest')}` | {m['params']} / {m['quantization']} | "
                   f"{m['cutoff'] or 'not documented (every case possibly seen)'} | {m['cutoff_source']} |")
    prompts_used = {}
    for d in list(res["e1"].values()) + list(res["s1"].values()):
        prompts_used[d["prompt"]["version"]] = d["prompt"]["sha256"]
    for h in res["hyde"].values():
        prompts_used[h["meta"]["prompt"]["version"]] = h["meta"]["prompt"]["sha256"]
    out += ["", "Prompt versions (sha256 of the template files; frozen before the first real run, see the report):", ""]
    out += [f"- `{v}`: `{sha}`" for v, sha in sorted(prompts_used.items())]
    any_doc = next(iter(list(res["e1"].values()) + list(res["s1"].values())), None)
    if any_doc:
        out += ["", f"LLM settings: {json.dumps(any_doc['settings'])}. Environments: " + "; ".join(sorted({
            f"repo `{d['environment'].get('repo_commit')}`{' (dirty)' if d['environment'].get('repo_dirty') else ''}, "
            f"{d['environment'].get('os')}, GPU {d['environment'].get('gpu') or 'none'}"
            for d in list(res["e1"].values()) + list(res["s1"].values())})) + "."]
    out.append("")
    for alias, doc in res["e1"].items():
        out += e1_section(alias, doc)
    for (alias, k), doc in res["s1"].items():
        out += s1_section(alias, k, doc)
    for alias, h in res["hyde"].items():
        out += hyde_section(alias, h)

    out += ["## Cost per case", "", "| Experiment | Model | Cases asked | Prompt tokens / case | Completion tokens / case | LLM seconds / case | Retried |",
            "|---|---|---|---|---|---|---|"]
    for a, d in res["e1"].items():
        out.append(_cost_row("E1", a, d["counts"]))
    for (a, k), d in res["s1"].items():
        out.append(_cost_row(f"S1 k={k}", a, d["counts"]))
    for a, h in res["hyde"].items():
        c = h["meta"]["counts"]
        n = max(c["cases"], 1)
        out.append(f"| HyDE | {a} | {c['cases']} | {c['input_tokens'] / n:.0f} | {c['output_tokens'] / n:.0f} | {c['llm_seconds'] / n:.1f} | - |")
    out += ["", "## What the LLM adds, and what it does not", "",
            "Read the main finding above and the paired tables. The numbers are for the models and prompts listed, on these case "
            "lists; they say nothing about other models or prompts. Cases the model may have seen in training are reported "
            "separately and are not part of the headline when a cutoff is documented. The ceiling from CP4 still applies: "
            "a function that is not among the candidates cannot be selected, whatever the model does.", ""]
    return "\n".join(out) + "\n"


def _cost_row(exp, alias, c) -> str:
    n = max(c["asked"], 1)
    return (f"| {exp} | {alias} | {c['asked']} | {c['input_tokens'] / n:.0f} | {c['output_tokens'] / n:.0f} | "
            f"{c['llm_seconds'] / n:.1f} | {c['retried']} |")
