"""`python -m vulntrace cp10 report`: `docs/results/CP10_VERDICT_RESULTS.md`, rendered from committed files.

The headline sentence (`HEADLINE`, `DIFFERENCE`, `HEADLINE_PENDING`) and every other fixed sentence
of this file were written before any D3c result existed (CP10 acceptance criterion 7); after the
D3c run only the numbers change. D3 and D3b are labelled IN-SAMPLE everywhere they appear.
"""

import json
from pathlib import Path
from typing import Any

from vulntrace.cp10 import score as sc
from vulntrace.paths import REPO_ROOT

RESULTS = REPO_ROOT / "docs" / "results" / "cp10"
OUT = REPO_ROOT / "docs" / "results" / "CP10_VERDICT_RESULTS.md"

HEADLINE = ("On the held-out set D3c ({apps} real Go applications, {cases} cases: {n_s} whose advisory has curated vulndb "
            "symbols, stratum S, and {n_n} without, stratum N), VulnTrace with the CP10 target hygiene was right on "
            "{h_k}/{h_n} REACHABLE verdicts with known truth (verdict precision {h_p} [95% Wilson {h_lo} to {h_hi}]) and "
            "gave {h_fnr} false NOT_REACHABLE; govulncheck was right on {g_k}/{g_n} of its REACHABLE claims ({g_p} "
            "[{g_lo} to {g_hi}]) and gave {g_fnr} false NOT_REACHABLE; {unknown} of {cases} cases have UNKNOWN truth.")
DIFFERENCE = {True: "The two precision intervals overlap: no detectable difference at this n.",
              False: "The two precision intervals do not overlap.",
              None: "At least one tool has no REACHABLE answer with known truth, so the precisions cannot be compared."}
HEADLINE_PENDING = ("Headline pending: the D3c verdict-level adjudication is not filled yet (state AWAITING_ADJUDICATION). "
                    "Numbers below that need truth are left blank.")
STRATUM_LINE = ("Stratum {st} ({cases} cases, {apps} applications): REACHABLE precision hygiene {h}, legacy {l}, "
                "govulncheck {g}; false NOT_REACHABLE hygiene {hf}, legacy {lf}, govulncheck {gf} (of {tr} truth-REACHABLE "
                "cases).")
GOVULN_STATEMENT = ("govulncheck is scored at its own level: in stratum S its REACHABLE claim is a symbol-level finding (a "
                    "curated vulnerable symbol is called); in stratum N, where the advisory has no curated symbols, a "
                    "package-level finding (the package is imported) or a module-level finding (the module is required) "
                    "is scored as its REACHABLE claim, because that is all it can say there. A more cautious answer is "
                    "not a win for either tool by itself; only adjudicated truth scores it.")
LIMITATIONS = [
    "D3c has a handful of applications chosen by written rules from a fixed candidate list; rates describe these cases, "
    "not Go software in general.",
    "Cases of one application share code, toolchain and dependencies, so they are not independent; Wilson intervals "
    "assume independence and therefore understate the uncertainty.",
    "Truth is adjudicated by reviewer agents and the supervisor reading the source, with an owner spot-check (the CP7b "
    "method). It is not expert human ground truth; reviewers of the same model family share blind spots.",
    "Truth asks whether any decision target is reachable by some route: the curated vulndb symbols in stratum S, the "
    "fix's changed non-context functions in stratum N. Reachability only, never exploitability.",
    "Stratum N includes UNREVIEWED (GHSA-imported) advisories, whose affected ranges and fix links the Go security team "
    "has not checked; both tools read the same pinned snapshot.",
    "D3 and D3b are IN-SAMPLE for CP10 (the hygiene rules were written after reading their adjudications); their "
    "earlier truths (CP7b, CP9) were judged on the legacy targets (the changed functions), while the CP10 truth-only "
    "items are judged on the hygiene targets.",
    "Analysis is for linux/amd64, CGO_ENABLED=0, no build tags, go1.26.10; other configurations can differ.",
]


def _read(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _pct(x: float) -> str:
    return f"{x:.2f}"


def _r(w: dict[str, Any]) -> str:
    return f"{w['k']}/{w['n']} = {_pct(w['rate'])} [{_pct(w['ci_low'])}, {_pct(w['ci_high'])}]" if w["n"] else "n/a (n = 0)"


def esc(x: Any) -> str:
    s = "" if x is None else str(x)
    for ch in ("\\", "|", "*", "_", "`", "<", ">", "[", "]"):
        s = s.replace(ch, "\\" + ch)
    return s


def headline(scores: dict[str, Any] | None, d3c_doc: dict[str, Any]) -> str:
    if scores is None:
        return HEADLINE_PENDING
    a = scores["ALL"]
    h, g = a["tools"]["hygiene"], a["tools"]["govulncheck"]
    hp, gp = h["reachable_precision"], g["reachable_precision"]
    text = HEADLINE.format(apps=a["apps"], cases=a["cases"], n_s=scores["S"]["cases"], n_n=scores["N"]["cases"],
                           h_k=hp["k"], h_n=hp["n"], h_p=_pct(hp["rate"]) if hp["n"] else "n/a",
                           h_lo=_pct(hp["ci_low"]), h_hi=_pct(hp["ci_high"]), h_fnr=h["false_not_reachable"]["count"],
                           g_k=gp["k"], g_n=gp["n"], g_p=_pct(gp["rate"]) if gp["n"] else "n/a",
                           g_lo=_pct(gp["ci_low"]), g_hi=_pct(gp["ci_high"]), g_fnr=g["false_not_reachable"]["count"],
                           unknown=a["unknown_truth"])
    return text + " " + DIFFERENCE[sc.intervals_overlap(hp, gp)]


def stratum_lines(scores: dict[str, Any]) -> list[str]:
    out = []
    for st in ("S", "N"):
        s = scores[st]
        t = s["tools"]
        out.append(STRATUM_LINE.format(st=st, cases=s["cases"], apps=s["apps"],
                                       h=_r(t["hygiene"]["reachable_precision"]), l=_r(t["legacy"]["reachable_precision"]),
                                       g=_r(t["govulncheck"]["reachable_precision"]),
                                       hf=t["hygiene"]["false_not_reachable"]["count"],
                                       lf=t["legacy"]["false_not_reachable"]["count"],
                                       gf=t["govulncheck"]["false_not_reachable"]["count"],
                                       tr=t["hygiene"]["false_not_reachable"]["truth_reachable_cases"]))
    return out


def tool_table(scores: dict[str, Any]) -> list[str]:
    out = ["| stratum | tool | cases run | answers | REACHABLE precision (truth R among R answers, known truth) | "
           "R answers with UNKNOWN truth | false NOT_REACHABLE (of truth-R cases) | CANT_DETERMINE rate |",
           "|---|---|---|---|---|---|---|---|"]
    for st in sc.STRATA:
        for t in sc.TOOLS:
            x = scores[st]["tools"][t]
            fnr = x["false_not_reachable"]
            out.append(f"| {st} | {t} | {x['ran']} | {esc(x['answers'])} | {_r(x['reachable_precision'])} | "
                       f"{x['reachable_unknown_truth']} | **{fnr['count']}** of {fnr['truth_reachable_cases']} | "
                       f"{_r(x['cant_determine_rate'])} |")
    return out


def counts_table(summary: dict[str, Any]) -> list[str]:
    out = ["| stratum | cases | VulnTrace hygiene | VulnTrace legacy | govulncheck claim | govulncheck level |",
           "|---|---|---|---|---|---|"]
    for st in ("S", "N", "ALL"):
        s = summary[st]
        out.append(f"| {st} | {s['cases']} | {esc(s['hygiene'])} | {esc(s['legacy'])} | {esc(s['govulncheck_claim'])} | "
                   f"{esc(s['govulncheck_level'])} |")
    return out


def paired_section(scores: dict[str, Any]) -> list[str]:
    out = []
    for st in sc.STRATA:
        for a in ("hygiene", "legacy"):
            p = scores[st]["paired"][a]
            out.append(f"- {st}, VulnTrace {a} vs govulncheck: both answered {p['both_answered']}, agree {p['agree']} "
                       f"({esc(p['agree_by_truth'])} by truth; both wrong: {esc(p['agree_both_wrong']) or 'none'}), "
                       f"disagree {len(p['disagree'])} (right: {esc(p['disagree_right']) or 'none'}), one abstained "
                       f"{len(p['one_abstained'])}; agreement {_r(p['agreement_rate'])}")
    dis = scores["ALL"]["paired"]["hygiene"]["disagree"]
    if dis:
        out += ["", "| case | VulnTrace hygiene | govulncheck | truth | right |", "|---|---|---|---|---|"]
        out += [f"| {esc(d['id'])} | {d['hygiene']} | {d['govulncheck']} | {d['truth']} | {d['right']} |" for d in dis]
    return out


def changes_section(scores: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    ch = scores["ALL"]["hygiene_changes"] if scores else None
    made_nr_s = summary["S"]["hygiene_made_not_reachable"]
    made_nr_n = summary["N"]["hygiene_made_not_reachable"]
    out = [f"- hygiene-induced NOT_REACHABLE in stratum N: **{len(made_nr_n)}** (the rules make this impossible; "
           f"listed if any: {esc(made_nr_n) or 'none'})",
           f"- hygiene-induced NOT_REACHABLE in stratum S: **{len(made_nr_s)}** ({esc(made_nr_s) or 'none'}); each is "
           "adjudicated below"]
    rows = ch if ch is not None else [{"id": i, "stratum": None, "legacy": None, "hygiene": None, "truth": None}
                                      for i in summary["ALL"]["hygiene_changed"]]
    if rows:
        out += ["", "| case | stratum | legacy | hygiene | truth | hygiene right | legacy right |", "|---|---|---|---|---|---|---|"]
        out += [f"| {esc(c['id'])} | {c.get('stratum')} | {c.get('legacy')} {esc(', '.join(c.get('legacy_reasons') or []))} | "
                f"{c.get('hygiene')} {esc(', '.join(c.get('hygiene_reasons') or []))} | {c.get('truth')} | "
                f"{c.get('hygiene_right')} | {c.get('legacy_right')} |" for c in rows]
    else:
        out.append("- no case changed verdict between the legacy and the hygiene targets")
    return out


def path_section(scores: dict[str, Any]) -> list[str]:
    out = ["| stratum | evidence level of the route shown | routes | judgements | path precision (CORRECT among "
           "CORRECT, INFEASIBLE_PATH, WRONG) | CANNOT_JUDGE |", "|---|---|---|---|---|---|"]
    for st in sc.STRATA:
        for lv, x in scores[st]["path_precision"].items():
            out.append(f"| {st} | {lv} | {x['routes']} | {esc(x['judgements'])} | {_r(x['precision'])} | {x['cannot_judge']} |")
    return out


def in_sample_truth(set_name: str, sheet: dict[str, Any] | None) -> dict[str, tuple[str, str]]:
    """{case id: (truth, source)} for D3 or D3b: the CP10 truth-only items, then the earlier sheets."""
    out: dict[str, tuple[str, str]] = {}
    if set_name == "d3":
        old = _read(REPO_ROOT / "docs" / "results" / "cp7b" / "adjudication" / "adjudication.json")
        for c in old["cases"]:
            if c.get("truth"):
                out[c["id"]] = (c["truth"], "CP7b sheet (legacy targets)")
    else:
        old = _read(REPO_ROOT / "docs" / "results" / "cp9" / "d3b" / "adjudication" / "adjudication.json")
        for c in old["cases"]:
            if c.get("truth"):
                out[c["id"]] = (c["truth"], "CP9 sheet (legacy targets)")
    for c in (sheet or {}).get("cases", []):
        if c["set"] == set_name and c.get("filled") and c.get("truth"):
            out[c["id"]] = (c["truth"], "CP10 truth-only item (hygiene targets)")
    return out


def in_sample_section(set_name: str, sheet: dict[str, Any] | None) -> list[str]:
    p = RESULTS / set_name / f"{set_name}_verdicts.json"
    if not p.is_file():
        return [f"No CP10 run of {set_name.upper()} is committed."]
    doc = _read(p)
    truths = in_sample_truth(set_name, sheet)
    truth = {k: v[0] for k, v in truths.items()}
    scores = sc.score_set(doc["rows"], truth)
    rep = doc.get("cp9_reproduction") or {}
    out = [f"**IN-SAMPLE, not evidence:** {esc(doc.get('label'))}", "",
           f"- cases {len(doc['rows'])}; truth available for {len(truth)} "
           f"({esc(dict(__import__('collections').Counter(s for _, s in truths.values())))})",
           f"- `--legacy-targets` against the committed CP9 verdicts (filter on, CP10 evidence keys removed): compared "
           f"{rep.get('compared')}, identical {len(rep.get('identical') or [])}, different {len(rep.get('different') or [])}, "
           f"missing {len(rep.get('missing') or [])}: identical = **{rep.get('all_identical')}**",
           f"- hygiene changed: {esc(doc['summary']['ALL']['hygiene_changed']) or 'none'}", ""]
    out += tool_table(scores)
    out += ["", "| case | stratum | hygiene | legacy | govulncheck claim (level) | truth | truth source |",
            "|---|---|---|---|---|---|---|"]
    for r in doc["rows"]:
        g = r.get("govulncheck") or {}
        t = truths.get(r["id"], (None, None))
        out.append(f"| {esc(r['id'])} | {r['stratum']} | {r['hygiene']['verdict']} {esc(', '.join(r['hygiene']['reason_codes'] or []))} | "
                   f"{r['legacy']['verdict']} {esc(', '.join(r['legacy']['reason_codes'] or []))} | {g.get('claim')} "
                   f"({g.get('level')}) | {t[0]} | {esc(t[1])} |")
    return out


def selection_section(sel: dict[str, Any] | None) -> list[str]:
    if not sel:
        return ["No D3c selection is committed."]
    out = [f"Rules: `{sel['rules']}` (written before any candidate was probed). Seed {sel['seed']}, toolchain "
           f"{esc(sel['toolchain'])}, vulndb `{sel['vulndb_commit'][:12]}`.", "",
           f"- candidates evaluated {sel['candidates_evaluated']} of {len(sel['candidates'])}; status counts "
           f"{esc(sel['status_counts'])}",
           f"- cases by stratum {esc(sel['totals'])}; quotas {esc(sel['quotas'])}; quotas met: **{sel['quotas_met']}**",
           f"- diversity: {esc(sel['diversity_note'])}", "",
           "| order | candidate | list | status | rule | detail |", "|---|---|---|---|---|---|"]
    for r in sel["candidates"]:
        if r["status"] == "NOT_EVALUATED_QUOTA_FILLED":
            continue
        out.append(f"| {r['order']} | {esc(r['repo'])} | {esc(r.get('source_list'))} | {r['status']} | {r['rule']} | "
                   f"{esc(r.get('detail'))} |")
    n_skip = sum(1 for r in sel["candidates"] if r["status"] == "NOT_EVALUATED_QUOTA_FILLED")
    out.append(f"\n{n_skip} further candidates were not evaluated (quotas met or the application limit reached).")
    return out


def render(d3c_doc: dict[str, Any], selection: dict[str, Any] | None, sheet: dict[str, Any] | None) -> str:
    filled = sheet is not None and not sc.validate(sheet, d3c_doc)
    d3c_sheet = {c["id"]: c for c in (sheet or {}).get("cases", []) if c["set"] == "d3c"}
    truth = {i: c["truth"] for i, c in d3c_sheet.items() if c.get("filled") and c.get("truth")}
    scores = sc.score_set(d3c_doc["rows"], truth, d3c_sheet) if filled else None
    s = d3c_doc["summary"]
    lines = ["# CP10 results: verdict-level trust against govulncheck", "",
             "Generated by `python -m vulntrace cp10 report` from committed files under `docs/results/cp10/`; do not "
             "edit by hand.", "", "## Headline", "", headline(scores, d3c_doc), ""]
    if scores:
        lines += stratum_lines(scores) + [""]
    lines += ["REACHABLE means reachable in the call graph from a `main` package, never exploitable. "
              "Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.", "",
              "## False NOT_REACHABLE (reported first)", ""]
    if scores:
        for st in sc.STRATA:
            lines.append(f"- {st}: " + "; ".join(
                f"{t} **{scores[st]['tools'][t]['false_not_reachable']['count']}** of "
                f"{scores[st]['tools'][t]['false_not_reachable']['truth_reachable_cases']} truth-REACHABLE cases "
                f"({esc(scores[st]['tools'][t]['false_not_reachable']['ids']) or 'none'})" for t in sc.TOOLS))
    else:
        lines.append("Pending adjudication.")
    lines += ["", "## Verdicts (D3c, held-out)", ""] + counts_table(s) + ["", GOVULN_STATEMENT, ""]
    if scores:
        lines += ["## Verdict-level scores against adjudicated truth (D3c)", ""] + tool_table(scores) + [""]
        lines += ["## Paired comparison with govulncheck (same cases)", ""] + paired_section(scores) + [""]
    lines += ["## What the target hygiene changed (D3c)", ""] + changes_section(scores, s) + [""]
    if scores:
        lines += ["## Path precision by evidence level (D3c, CP10 verdicts)", ""] + path_section(scores) + [""]
    lines += ["## D3 (CP7b applications), IN-SAMPLE", ""] + in_sample_section("d3", sheet) + [""]
    lines += ["## D3b (CP9 applications), IN-SAMPLE", ""] + in_sample_section("d3b", sheet) + [""]
    lines += ["## Selection of D3c", ""] + selection_section(selection) + [""]
    lines += ["## Run", "",
              f"- pipeline: {esc(d3c_doc.get('pipeline'))}",
              f"- toolchain: {esc(d3c_doc.get('toolchain'))}; env {esc(d3c_doc.get('env'))}",
              f"- govulncheck: {esc(d3c_doc.get('govulncheck'))}",
              f"- seconds per case: {esc(d3c_doc.get('seconds_per_case'))}",
              f"- verdict provenance: {esc(d3c_doc.get('verdict_provenance'))}", ""]
    lines += ["## Limitations", ""] + [f"- {x}" for x in LIMITATIONS]
    return "\n".join(lines) + "\n"


def cmd_report(args, log) -> int:
    p = RESULTS / "d3c" / "d3c_verdicts.json"
    if not p.is_file():
        log(f"missing prerequisite: {p}")
        return 3
    d3c = _read(p)
    sel_p = RESULTS / "d3c" / "d3c_selection.json"
    sheet_p = RESULTS / "adjudication" / "adjudication.json"
    sheet = _read(sheet_p) if sheet_p.is_file() else None
    if sheet is not None:
        errors = sc.validate(sheet, d3c)
        if errors and not args.allow_unfilled:
            log("the adjudication sheet cannot be scored yet (use --allow-unfilled for a preview):")
            for e in errors[:20]:
                log("  " + e)
            return 2
    elif not args.allow_unfilled:
        log(f"missing prerequisite: {sheet_p} (use --allow-unfilled for a preview)")
        return 3
    text = render(d3c, _read(sel_p) if sel_p.is_file() else None, sheet)
    out = Path(args.out) if args.out else OUT
    out.write_text(text, encoding="utf-8")
    log(f"wrote {out}")
    return 0
