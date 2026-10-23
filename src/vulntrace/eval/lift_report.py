"""The generated CP5b results document (`docs/results/CP5B_LIFTING_RESULTS.md`).

Every number is read from `lift_d1.json` and `lift_d4_ceiling.json` (written by `eval lift`) and
formatted here; nothing is typed by hand. Wording rule (as in CP5): a method is called better or
worse only when the paired 95% interval excludes 0, and every rate is printed with its
denominator and its coverage.
"""

import json
from pathlib import Path
from typing import Any

from vulntrace.eval.llm_report import _ci, _f, verdict

RULES = ("NEAREST", "ALL")
VARIANT_LABEL = {"replace/NEAREST": "E1+L replace, NEAREST", "replace/ALL": "E1+L replace, ALL",
                 "add/NEAREST": "E1+L add, NEAREST", "add/ALL": "E1+L add, ALL"}


def _rate(r: dict[str, Any]) -> str:
    return f"{r['count']}/{r['of']} ({_f(r['rate'])})" if r["of"] else f"0/0"


def _metric_row(label: str, s: dict[str, Any]) -> str:
    if not s.get("n"):
        return f"| {label} | 0 | - | - | - | - | - |"
    p = s["precision"]
    prec = "-" if not p else f"{_ci(p)} (n={p['n_with_prediction']})"
    return (f"| {label} | {s['n']} ({s['n_clusters']}) | {prec} | {_ci(s['recall'])} | {_ci(s['f1'])} | {_ci(s['any_hit'])} | "
            f"{_ci(s['exact'])} |")


def _lifting_section(d: dict[str, Any]) -> list[str]:
    L = d["lifting"]
    n = L["cases_with_derived"]
    cov = L["coverage"]
    out = ["## 1. Lifting against the vulndb's `derived_symbols` (D1)", "",
           f"Population: the D1 cases whose vulndb record has non-empty `derived_symbols`: **{n}** of {d['case_list']['cases']} D1 cases "
           f"({L['clusters']} clusters by fix commit). Seeds are each case's core symbols; gold is the `derived_symbols`, compared by name. "
           f"The source is the vulnerable side (parent of the first fix commit), dependencies from the Go module proxy, "
           f"`GOTOOLCHAIN=local`, `CGO_ENABLED=0`; nothing from the analysed code was run.", "",
           "| Step | Cases | Of |", "|---|---|---|",
           f"| attempted | {n} | {n} |", f"| helper loaded the module (any seed answered) | {L['module_loaded']} | {n} |",
           f"| **lifted at least one core seed (LIFTED or ALREADY_EXPORTED)** | **{cov['lifted_ok']}** | {n} ({_f(cov['rate'])}) |",
           f"| of the lifted cases, those whose tree had no go.mod (synthesised, see section 4) | {L['lifted_with_synthesized_go_mod']} | {cov['lifted_ok']} |", ""]
    if L["failure_counts"]:
        out += ["**Why the other cases did not lift** (counted, never dropped):", "", "| Reason | Cases | First examples (first error line) |", "|---|---|---|"]
        for reason, k in L["failure_counts"].items():
            ex = "; ".join(f"`{e['id']}`: {str(e['detail'])[:110]}" for e in L["failure_detail"][reason][:3])
            out.append(f"| {reason} | {k} | {ex} |")
        out.append("")
    out += ["Scores below are macro-averages over cases with a cluster-bootstrap 95% interval (resampling D1 `cluster_key`). "
            "`n (clusters)` is the case count; precision is averaged only over cases that predicted something (n shown). "
            "**literal** scores the whole lifted set against `derived_symbols`; **new only** drops the seed symbols themselves "
            "(a seed that is already exported lifts to itself, which is not a derived symbol), the fairer view of what lifting adds.", ""]
    head = ["| Rule · view · population | n (clusters) | precision | recall | F1 | any-hit | exact |", "|---|---|---|---|---|---|---|"]
    out += head
    for rule in RULES:
        for view, vlabel in (("literal", "literal"), ("new_only", "new only")):
            for pop, plabel in (("on_lifted", f"cases that lifted ({cov['lifted_ok']}/{n})"), ("all_attempted", f"all attempted, failure = nothing predicted ({n}/{n})")):
                out.append(_metric_row(f"{rule} · {vlabel} · {plabel}", L["rules"][rule][view][pop]))
    out.append("")
    sz = {r: L["rules"][r]["lifted_set_size"] for r in RULES}
    out += [f"Mean lifted-set size on cases that lifted: NEAREST {_f(sz['NEAREST']['mean'])} (max {sz['NEAREST']['max']}), "
            f"ALL {_f(sz['ALL']['mean'])} (max {sz['ALL']['max']}).", ""]
    if "all_minus_nearest" in L:
        a = L["all_minus_nearest"]
        out += [f"**ALL minus NEAREST, paired over the {a['n']} cases that lifted (literal view):** "
                f"recall {_ci(a['recall'])}: {verdict(a['recall'])}; precision (zeros for empty) {_ci(a['precision0'])}: {verdict(a['precision0'])}; "
                f"F1 {_ci(a['f1'])}: {verdict(a['f1'])}.", ""]
    ex = d.get("examples", {})
    if ex.get("exact") or ex.get("different"):
        out += ["**Worked examples** (first cases by id, chosen before looking at outcomes; ALL rule). "
                "A difference is either the curator's convention or a miss: read the two lists, not the score.", ""]
        for kind, title in (("exact", "lifted set minus seeds equals the curator's derived symbols"), ("different", "lifted set differs from the derived symbols")):
            for e in ex.get(kind, []):
                out.append(f"- `{e['id']}` ({title}): core {e['core']}; derived {e['derived']}; lifted NEAREST {e['NEAREST']}, ALL {e['ALL']}")
        out.append("")
    return out


def _e1l_section(d: dict[str, Any]) -> list[str]:
    out = ["## 2. E1+L: the committed E1 selections, lifted", "",
           "E1 is the CP5 experiment (an LLM chooses among the functions a fix commit changed). **No model was run in CP5b**: the "
           "committed selections in `docs/results/cp5/` are mapped back to functions through the rebuilt D1 evidence, the recomputed E1 and E0 "
           "metrics are checked against the committed ones case by case (a case that does not reproduce is excluded and counted), "
           "and each selected function is sent through the same `lift` run. Variants: **replace** (a selected function that lifted is "
           "replaced by its entry points; one that did not lift stays, origin ROOT_ONLY) and **add** (selection plus entry points), each with "
           "the NEAREST and ALL rule. Gold is core ∪ derived (primary) and core only. E0, E1 and E1+L are scored on the same cases.", ""]
    block = d.get("e1_plus_l", {})
    if not block:
        return out + ["Not run: no E1 result files were found.", ""]
    for alias, b in block.items():
        s = b["summary"]
        out += [f"### `{alias}`", "", f"Cases used: {b['rows_used']}; excluded: {b['skipped'] or 'none'}.", ""]
        for key in ("headline", "all"):
            g = s.get(key)
            if not g or not g.get("n"):
                out += [f"**{(g or {}).get('label', key)}**: no cases.", ""]
                continue
            out += [f"**{g['label']}**: {g['n']} cases ({g['n_clusters']} clusters); lifting applied to {g['lifting_applied']} "
                    f"(a loaded module and at least one lifted selection), and it changed the selection in {g['selection_changed']}. "
                    f"Where lifting did not apply, E1+L equals E1.", ""]
            for gold, glabel in (("core_derived", "core ∪ derived (primary)"), ("core", "core only")):
                gg = g[gold]
                out += [f"*Gold: {glabel}*", "", "| Method | precision | recall | F1 | any-hit | Δ F1 vs E1 | Δ recall vs E1 | Δ F1 vs E0 | Δ recall vs E0 |",
                        "|---|---|---|---|---|---|---|---|---|"]
                for m, label in (("e0", "E0 (all changed functions)"), ("e1", "E1"), *VARIANT_LABEL.items()):
                    sm = gg["summary"][m]
                    if m in VARIANT_LABEL:
                        pe, p0 = gg["paired_vs_e1"][m], gg["paired_vs_e0"][m]
                        cells = [_ci(pe["f1"]) + " " + _short(pe["f1"]), _ci(pe["recall"]) + " " + _short(pe["recall"]),
                                 _ci(p0["f1"]) + " " + _short(p0["f1"]), _ci(p0["recall"]) + " " + _short(p0["recall"])]
                    else:
                        cells = ["-"] * 4
                    out.append(f"| {label} | {_ci(sm['precision0'])} | {_ci(sm['recall'])} | {_ci(sm['f1'])} | {_ci(sm['any_hit'])} | " + " | ".join(cells) + " |")
                out.append("")
                if gold == "core_derived" and "applied_only" in gg:
                    a = gg["applied_only"]
                    out += [f"*Only the {a['n']} cases where lifting applied ({a['n_clusters']} clusters), paired with E1:* " + "; ".join(
                        f"{VARIANT_LABEL[m]}: F1 {_ci(a['paired_vs_e1'][m]['f1'])}, recall {_ci(a['paired_vs_e1'][m]['recall'])}"
                        for m in VARIANT_LABEL) + ".", ""]
    return out


def _short(d: dict[str, float]) -> str:
    if not d.get("n"):
        return ""
    return "↑" if d["ci_low"] > 0 else ("↓" if d["ci_high"] < 0 else "·")


def _ceiling_section(c: dict[str, Any] | None) -> list[str]:
    out = ["## 3. D4 ceiling: could graph expansion reach a missed core symbol?", ""]
    if c is None:
        return out + ["Not run: `lift_d4_ceiling.json` was not found.", ""]
    s = c["summary"]
    out += [f"Measurement only; no pipeline change. A **ceiling case** is a D4 case whose core symbols are not among the range's changed functions "
            f"(name level): **{s['ceiling_cases']}** of the {s['d4_cases']} D4 cases ({s['without_evidence']} have no candidates at all and are not counted). "
            f"For each, the helper's VTA graph of the module at the range's `from` commit is queried for callers and callees up to {c['settings']['max_hops']} hops of the core symbols; "
            f"the question is whether any candidate that exists at that commit is on the other end.", "",
            "| Step | Cases | Of |", "|---|---|---|",
            f"| ceiling cases | {s['ceiling_cases']} | {s['d4_cases']} |",
            f"| module prepared (go.mod found or synthesised, dependencies resolved) | {s['prepared']} | {s['ceiling_cases']} |",
            f"| of those, the synthesised-go.mod cases | {s['synthesized_go_mod']} | {s['prepared']} |",
            f"| graph loaded and the core symbol found | {s['loaded_with_core_found']} | {s['ceiling_cases']} |",
            f"| **a candidate within 1 hop (caller or callee)** | **{_rate(s['within_1'])}** | graph cases ({s['loaded_with_core_found']}); of all ceiling cases {_rate(s['within_1_of_all_ceiling_cases'])} |",
            f"| **a candidate within 2 hops** | **{_rate(s['within_2'])}** | graph cases; of all ceiling cases {_rate(s['within_2_of_all_ceiling_cases'])} |", ""]
    if s["failure_counts"]:
        out += ["Cases without a usable graph: " + ", ".join(f"{k} {v}" for k, v in s["failure_counts"].items()) + ". First error lines:", ""]
        seen = {}
        for r in c["rows"]:
            if r["failure"] and r["failure"] not in seen:
                seen[r["failure"]] = []
            if r["failure"] and len(seen[r["failure"]]) < 3:
                seen[r["failure"]].append(f"`{r['id']}`: {str(r['detail'])[:110]}")
        for k, v in seen.items():
            out.append(f"- {k}: " + "; ".join(v))
        out.append("")
    out += ["By direction (a candidate calls the core symbol = *callers*; the core symbol calls a candidate = *callees*), cases with a graph:", "",
            "| Direction | within 1 hop | within 2 hops |", "|---|---|---|"]
    for dname, v in s["by_direction"].items():
        out.append(f"| {dname} | {_rate(v['within_1'])} | {_rate(v['within_2'])} |")
    out += ["", "By candidate-set size (a big candidate set makes 'some candidate is nearby' likely by itself, so read the rows, not the total):", "",
            "| Candidates | graph cases | within 1 hop | within 2 hops |", "|---|---|---|---|"]
    for label, v in s["by_size"].items():
        out.append(f"| {label} | {v['n']} | {_rate(v['within_1'])} | {_rate(v['within_2'])} |")
    if s["expanded_candidates_median"] is not None:
        out += ["", f"Where a candidate was within 2 hops, the median number of distinct candidates within 2 hops was {s['expanded_candidates_median']}."]
    out.append("")
    return out


def _limitations() -> list[str]:
    return ["## 4. What these numbers do not show", "",
            "- **Convention.** `derived_symbols` follow a curator's choice. A seed that is already exported lifts to itself by the rule, while the curators often "
            "also listed the callers further up (for example the servers and run loops that call an exported API). A low score can be that convention and not a bug; "
            "the worked examples show both.",
            "- **Callbacks through dependencies are not followed.** The upward walk stays inside the packages the request matched. A call that goes into a dependency "
            "and back (a handler registered with a framework, `sort.Slice`) shows up only when the callee is an exported method or function itself.",
            "- **Promoted methods.** A method promoted through an embedded field is a synthetic wrapper in the graph and is not counted as an entry point.",
            "- **One source tree per case.** The tree is the parent of the first fix commit; cases with several fix commits or several modules use that tree.",
            "- **No cgo, one platform.** `CGO_ENABLED=0` on linux/amd64: cgo-only packages and other platforms' files are not loaded; build tags are not varied.",
            "- **Synthesised go.mod.** A tree that predates Go modules gets a `go.mod` with the vulndb module path and `go mod tidy -e`; the result may resolve different dependency versions than the project used then.",
            "- **Generic seeds** are reported `UNSUPPORTED_SYMBOL_FORM` and count as failures.",
            "- **Name-level matching** (not package path), as everywhere in this project.", ""]


def render_cp5b_doc(results_dir: Path, source: str) -> str:
    d1_path, d4_path = Path(results_dir) / "lift_d1.json", Path(results_dir) / "lift_d4_ceiling.json"
    d1 = json.loads(d1_path.read_text(encoding="utf-8")) if d1_path.is_file() else None
    d4 = json.loads(d4_path.read_text(encoding="utf-8")) if d4_path.is_file() else None
    out = ["# CP5b results: lifting and caller/callee queries", "",
           f"Generated by `python -m vulntrace results render --doc cp5b` from `{source}`. Do not edit by hand.", ""]
    if d1 is None and d4 is None:
        return "\n".join(out + ["No result files were found; run `python -m vulntrace eval lift --set d1` first.", ""]) + "\n"
    out += ["## Main findings", ""]
    if d1:
        L = d1["lifting"]
        n, cov = L["cases_with_derived"], L["coverage"]
        near, allr = L["rules"]["NEAREST"]["new_only"]["on_lifted"], L["rules"]["ALL"]["new_only"]["on_lifted"]
        out += [f"- **Coverage first:** lifting ran on {cov['lifted_ok']} of the {n} D1 cases that have `derived_symbols` ({_f(cov['rate'])}); "
                f"the module loaded in {L['module_loaded']}. The rest are listed by reason in section 1.",
                f"- **Against the curators' derived symbols** (new symbols only, cases that lifted, n={near.get('n', 0)}): "
                f"NEAREST precision {_ci(near['precision']) if near.get('precision') else '-'}, recall {_ci(near['recall']) if near.get('n') else '-'}; "
                f"ALL precision {_ci(allr['precision']) if allr.get('precision') else '-'}, recall {_ci(allr['recall']) if allr.get('n') else '-'}."]
        for alias, b in d1.get("e1_plus_l", {}).items():
            g = b["summary"].get("headline")
            if not g or not g.get("n"):
                continue
            best = []
            for m, label in VARIANT_LABEL.items():
                p = g["core_derived"]["paired_vs_e1"][m]["f1"]
                best.append(f"{label}: F1 Δ {_ci(p)} ({verdict(p).split(' (')[0]})")
            out.append(f"- **E1+L, `{alias}`** (headline group, {g['n']} cases, gold core ∪ derived, paired with E1): " + "; ".join(best) + ".")
    if d4:
        s = d4["summary"]
        out.append(f"- **D4 ceiling:** of {s['ceiling_cases']} cases whose core symbol is not a candidate, the graph was usable in {s['loaded_with_core_found']}; "
                   f"a candidate lies within 1 hop in {_rate(s['within_1'])} and within 2 hops in {_rate(s['within_2'])} of those.")
    out.append("")
    if d1:
        e = d1["environment"]
        out += ["## Run", "", f"- Command: `{e['command']}`", f"- Machine: {e['machine']}, {e['os']}; {e.get('go')}; Python {e['python']}; "
                f"repository commit {e['repo_commit']}{' (dirty)' if e.get('repo_dirty') else ''}; {e['jobs']} case(s) in parallel.",
                f"- Time: {e['wall_seconds_this_invocation']} s wall clock for this invocation; {e['per_case_seconds_total']} s summed over cases "
                f"(first-time module downloads dominate). {e.get('gomodcache_note', '')}",
                f"- Settings: rules {d1['settings']['rules']}, depth limit {d1['settings']['max_lift_depth']}; {d1['settings']['walk']}.", ""]
        out += _lifting_section(d1)
        out += _e1l_section(d1)
    out += _ceiling_section(d4)
    out += _limitations()
    return "\n".join(out) + "\n"
