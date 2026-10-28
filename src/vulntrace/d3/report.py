"""Renders `docs/results/CP7B_REAL_APPS_RESULTS.md` (CP7b deliverable 5) from committed files only:
`cp7b/d3_selection.json`, `cp7b/d3_cases.json`, `cp7b/d3_triage.json`, `cp7b/verdicts/*.json` and the
filled `cp7b/adjudication/adjudication.json`.

The headline sentence (`HEADLINE` and `HEADLINE_NO_REACHABLE`) was fixed in this file before any D3
triage result existed and is not edited after results are seen; only the numbers fill it.
"""

from typing import Any

from vulntrace.d3 import score as sc
from vulntrace.d3 import sheet as sh

TITLE = "CP7b results: real Go applications (D3), adjudicated"

# Fixed before any D3 result (CP7b specification, deliverable 5). Do not edit after results.
HEADLINE = ("On {apps} real Go applications ({cases} application-advisory cases), VulnTrace answered {answered} cases and "
            "abstained (CANT_DETERMINE) on {cd}; adjudication judged {r_correct} of {r_decided} REACHABLE paths correct "
            "(precision {r_prec}, 95% Wilson interval {r_lo} to {r_hi}) and found {fnr} false NOT_REACHABLE among "
            "{nr_adj} adjudicated NOT_REACHABLE verdicts.")
HEADLINE_NO_REACHABLE = ("On {apps} real Go applications ({cases} application-advisory cases), VulnTrace answered {answered} "
                         "cases and abstained (CANT_DETERMINE) on {cd}; no REACHABLE path could be judged, and adjudication "
                         "found {fnr} false NOT_REACHABLE among {nr_adj} adjudicated NOT_REACHABLE verdicts.")

FIXED_LIMITATIONS = [
    "Five applications are case studies, not a sample of Go software: rates below describe these cases only.",
    "Cases of one application share code, toolchain and dependencies, so they are not independent; Wilson intervals "
    "assume independence and therefore understate the uncertainty.",
    "Truth is human adjudication of the call path (reachability), not exploitability, and it was done by the owner and "
    "the supervising assistant, who also built or reviewed the system.",
    "Applications are pinned to releases from 2025 or earlier (selection rule A3); their current versions may differ.",
    "Selection rule V1 requires a GitHub fix commit, which excludes most golang.org/x advisories (fix links are "
    "go.dev/cl); D3 therefore says nothing about those.",
    "Mode 1 targets are every function the fix commit changed, at the fix commit's parent. When the application's "
    "dependency version is older or newer than that parent, a target can be missing (an ERROR, so CANT_DETERMINE) or "
    "can differ from the code the application really uses.",
    "Analysis is for linux/amd64, CGO_ENABLED=0, no build tags; other build configurations can differ.",
    "govulncheck is a reference, not truth: it checks the advisory's exported symbols, while Mode 1 checks the changed "
    "functions, so the two answer related but different questions.",
]


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _rate(r: dict[str, Any]) -> str:
    if not r or not r.get("n"):
        return "n/a (0 cases)"
    return f"{r['k']}/{r['n']} = {_pct(r['rate'])} [{_pct(r['ci_low'])}, {_pct(r['ci_high'])}]"


def headline(s: dict[str, Any]) -> str:
    p = s["reachable"]["precision"]
    args = dict(apps=s["apps"], cases=s["cases"], answered=s["answered"], cd=s["verdicts"]["CANT_DETERMINE"],
                fnr=s["false_not_reachable"]["found"], nr_adj=s["false_not_reachable"]["adjudicated"])
    if not p["n"]:
        return HEADLINE_NO_REACHABLE.format(**args)
    return HEADLINE.format(**args, r_correct=p["k"], r_decided=p["n"], r_prec=_pct(p["rate"]), r_lo=_pct(p["ci_low"]),
                           r_hi=_pct(p["ci_high"]))


def _table(head: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(sh.md(c) if not str(c).startswith("`") else str(c) for c in r) + " |" for r in rows]
    return out


def _example(title: str, cid: str | None, rows: dict[str, dict], adj: dict[str, dict], verdicts: dict[str, dict]) -> list[str]:
    out = [f"### {title}", ""]
    if cid is None:
        return out + ["No case of this kind.", ""]
    r, a, v = rows[cid], adj.get(cid) or {}, verdicts.get(cid) or {}
    out.append(f"- case {sh.code_span(cid)}: advisory {sh.code_span(r['advisory'])} in {sh.code_span(r['app_repo'])} "
               f"{sh.code_span(r.get('app_tag'))}, module {sh.code_span(str(r.get('module')) + '@' + str(r.get('version_selected')))}")
    out.append(f"- verdict **{sh.md(r.get('verdict'))}**, reasons {sh.md(', '.join(r.get('reason_codes') or []) or 'none')}, "
               f"mode {sh.md(r.get('mode'))}, per-symbol results {sh.md(r.get('entries'))}")
    if r.get("govulncheck"):
        g = r["govulncheck"]
        out.append(f"- govulncheck (reference): {sh.md(g.get('verdict'))} at level {sh.md(g.get('level'))}, "
                   f"agreement {sh.md(g.get('agreement'))}")
    out.append(f"- adjudication: {sh.md(a.get('adjudication') or 'not adjudicated')}"
               + (f" by {sh.md(a.get('by'))}" if a.get("by") else "")
               + (f"; truth {sh.md(a.get('truth'))}" if a.get("truth") else "")
               + (f"; note: {sh.md(a.get('note'))}" if a.get("note") else ""))
    paths = sh.reachable_paths(v) if v else []
    if paths:
        p = paths[0]
        out += ["", f"Path to {sh.code_span(p['target'])} from {sh.code_span(p['main'])}:", ""]
        for i, e in enumerate(p["path"]["edges"], start=1):
            cs = e.get("call_site") if (e.get("call_site") or {}).get("file") else {}   # Go's synthetic edges have none
            where = sh.code_span(f"{cs.get('file')}:{cs.get('line')}") if cs else "(synthetic edge)"
            out.append(f"{i}. {sh.code_span(e['caller'])} calls {sh.code_span(e['callee'])} at {where} ({sh.md(e.get('kind'))})")
    return out + [""]


def render(selection: dict[str, Any], case_doc: dict[str, Any], triage_doc: dict[str, Any], sheet: dict[str, Any],
           verdicts: dict[str, dict]) -> str:
    s = sc.score(sheet, triage_doc)
    ex = sc.pick_examples(sheet, triage_doc)
    rows = {r["id"]: r for r in triage_doc["rows"]}
    adj = {c["id"]: c for c in sheet["cases"] if c.get("adjudication")}
    tsum = triage_doc["summary"]
    out = [f"# {TITLE}", "", "Generated by `python -m vulntrace d3 report` from committed files; do not edit by hand.", "",
           "## Headline", "", headline(s), "",
           "REACHABLE means reachable in the call graph from a `main` package, never exploitable.", ""]
    f = s["false_not_reachable"]
    out += ["## False NOT_REACHABLE (reported first)", "",
            f"Adjudicated {f['adjudicated']} of {f['of_total']} NOT_REACHABLE verdicts; judged WRONG (a false NOT_REACHABLE): "
            f"**{f['found']}**" + (f" ({', '.join(sh.code_span(i) for i in f['ids'])})" if f["ids"] else "") +
            f"; CANNOT_JUDGE: {f['cannot_judge']}.", ""]
    v = s["verdicts"]
    out += ["## Verdicts", ""] + _table(["verdict", "cases"], [[k, v[k]] for k in ("REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE")]
                                        + [["not triaged (harness or preparation failure)", s["not_triaged"]]]) + [""]
    out += [f"Modes: {sh.md(tsum.get('modes'))}. Before the Mode 2 policy: {sh.md(tsum.get('pre_policy_verdicts'))}.", ""]
    r = s["reachable"]
    out += ["## REACHABLE precision (adjudicated)", "",
            f"- adjudicated {r['adjudicated']} of {r['of_total']}; counts {sh.md(r['counts'])}",
            f"- precision (CORRECT among CORRECT, INFEASIBLE_PATH, WRONG): {_rate(r['precision'])}",
            f"- the path exists in the code (CORRECT or INFEASIBLE_PATH): {_rate(r['path_exists_rate'])}",
            f"- CANNOT_JUDGE (left out of both rates): {r['cannot_judge']}", ""]
    c = s["cant_determine"]
    out += ["## CANT_DETERMINE", "", f"- share of triaged cases: {_rate(c['share'])}",
            f"- adjudicated {c['adjudicated']}: {sh.md(c['counts'])}; truth by reading the code: {sh.md(c['truth'])}", ""]
    out += _table(["reason codes", "cases"], [[k, n] for k, n in sorted(c["reasons"].items())]) + [""]
    nr = s["not_reachable"]
    out += ["## NOT_REACHABLE (adjudicated sample)", "", f"- adjudicated {nr['adjudicated']}: {sh.md(nr['counts'])}; "
            f"correct among CORRECT and WRONG: {_rate(nr['correct'])}", ""]
    g = s["govulncheck"]
    gd = (triage_doc.get("govulncheck") or {})
    out += ["## Reference: govulncheck (not truth)", "",
            f"govulncheck {sh.md(gd.get('version', 'not run'))}, {sh.md(gd.get('mode', ''))}, database: {sh.md(gd.get('db', ''))}.", "",
            f"- cases compared: {g['compared']}; agreement {sh.md(g['agreement'])}",
            f"- agreement where both answered REACHABLE or NOT_REACHABLE: {_rate(g['agree_rate'])}",
            f"- govulncheck reported nothing for: {sh.md(', '.join(tsum['govulncheck']['not_affected']) or 'none')}", ""]
    dis = tsum["govulncheck"]["disagreements"]
    if dis:
        out += _table(["case", "ours", "govulncheck", "govulncheck level", "adjudication"],
                      [[d["id"], d["ours"], d["govulncheck"], d["level"], (adj.get(d["id"]) or {}).get("adjudication") or "-"]
                       for d in dis]) + [""]
    else:
        out += ["No disagreement.", ""]
    out += ["## Per application", ""]
    out += _table(["application", "tag", "verdicts and adjudications"],
                  [[a, next((x.get("app_tag") for x in rows.values() if x["app_repo"] == a), ""), counts]
                   for a, counts in s["per_app"].items()]) + [""]
    out += ["## Worked examples", "", "Chosen by a fixed rule (smallest case id of each kind; see `score.pick_examples`).", ""]
    out += _example("A REACHABLE case", ex["reachable"], rows, adj, verdicts)
    out += _example("A CANT_DETERMINE case", ex["cant_determine"], rows, adj, verdicts)
    out += _example("A disagreement with govulncheck", ex["disagreement"], rows, adj, verdicts)
    counts = selection.get("status_counts") or {}
    reached_load = sum(n for k, n in counts.items() if k in ("LOAD_FAILED", "NO_MAIN", "TOO_MANY_MAINS", "BUILD_FAILED",
                                                            "NO_ELIGIBLE_ADVISORY_SELECTED", "KEPT"))
    out += ["## Selection", "",
            f"Rules: `{selection.get('rules')}` (written before any candidate was probed). Toolchain {sh.md(selection.get('toolchain'))}, "
            f"vulndb {sh.code_span((selection.get('vulndb_commit') or '')[:12])}.", "",
            f"- candidates: {len(selection.get('candidates') or [])}; status counts: {sh.md(counts)}",
            f"- load rate: of {reached_load} candidates that reached the load step (A8), "
            f"{reached_load - counts.get('LOAD_FAILED', 0)} loaded and "
            f"{counts.get('KEPT', 0) + counts.get('NO_ELIGIBLE_ADVISORY_SELECTED', 0)} built every main package",
            f"- diversity: {sh.md(selection.get('diversity_note'))}", ""]
    out += _table(["order", "candidate", "status", "rule", "detail"],
                  [[x["order"], x["repo"], x["status"], x["rule"], x.get("detail", "")] for x in selection.get("candidates") or []]) + [""]
    sec = tsum.get("seconds_per_case") or {}
    out += ["## Cost and environment", "",
            f"- seconds per case (including evidence and verification): p50 {sec.get('p50')}, p95 {sec.get('p95')}, "
            f"max {sec.get('max')}, total {sec.get('total')}",
            f"- toolchain: helper {sh.md(tsum['toolchain']['helper'])}, linker {sh.md(tsum['toolchain']['linker'])}; "
            f"{sh.md(triage_doc.get('env'))}",
            f"- run: {sh.code_span((triage_doc.get('environment') or {}).get('command'))} at repository commit "
            f"{sh.code_span((triage_doc.get('environment') or {}).get('repo_commit'))}",
            f"- adjudicated by: {sh.md(s['adjudicated_by'])}", ""]
    out += ["## Limitations", ""] + [f"- {x}" for x in FIXED_LIMITATIONS]
    if s["not_triaged"]:
        out.append(f"- {s['not_triaged']} case(s) could not be triaged (see the triage file); they are counted, not dropped.")
    if s["extra_adjudications"]:
        out.append(f"- {len(s['extra_adjudications'])} case(s) outside the sample were adjudicated as well and are included.")
    return "\n".join(out) + "\n"
