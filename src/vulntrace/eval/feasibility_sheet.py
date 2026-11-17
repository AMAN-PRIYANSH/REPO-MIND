"""`python -m vulntrace cp9 sheet`: adjudication sheets for D3b (CP9 deliverable 4), in the CP7b format.

Every case whose verdict is REACHABLE in either run (filter off or on; the filter is downgrade-only,
so this is every case REACHABLE without it) gets a section: path A, the verified path without the
filter; then either path B, the path that passed the filter (the verified path with it), or, for a
downgraded case, the infeasible steps the filter reported, each with its code lines. All per-case
values are copied from the verdict files or read from the analysed source files (CP7b helpers
`d3.sheet`: escaping of untrusted text, source links, source lines). The only prose is the fixed
instruction text. The builder prepares; the supervisor fills `adjudication.json`.
"""

import json
from pathlib import Path
from typing import Any

from vulntrace.d3 import sheet as s7

SCHEMA_VERSION = "1.0"
ADJUDICATIONS = ("CORRECT", "INFEASIBLE_PATH", "WRONG", "CANNOT_JUDGE")
ON_ADJUDICATIONS = ADJUDICATIONS + ("SAME_AS_OFF",)
STEP_JUDGEMENTS = ("YES", "NO", "PARTLY", "CANNOT_JUDGE")
TRUTHS = ("REACHABLE", "NOT_REACHABLE", "UNKNOWN")
MAX_ENTRIES = 3
MAX_STEPS = 3

INSTRUCTIONS = """How to adjudicate (the same text for every case; the CP7b method):

- Judge **reachability**, not exploitability. Every case below was REACHABLE without the filter.
- `adjudication_off`: path A (the verified path without the filter): `CORRECT` if every step is a real call that can
  run in the application; `INFEASIBLE_PATH` if the calls exist but the path cannot run as a whole; `WRONG` if a step
  does not exist or does not call the next function; `CANNOT_JUDGE` otherwise.
- `adjudication_on`: only if the case is still REACHABLE with the filter: the same judgement for path B (the path that
  passed the filter). `SAME_AS_OFF` is pre-filled by code when path B is path A.
- `steps_correct`: only if the filter downgraded the case: are the reported infeasible steps really impossible for the
  stated reason? `YES`, `NO`, `PARTLY` or `CANNOT_JUDGE`.
- `truth`: is the target (any listed reachable target) reachable from a `main` package by **some** path, reading the
  code? `REACHABLE`, `NOT_REACHABLE` or `UNKNOWN`. For a downgraded case, `REACHABLE` means the filter hid a real path
  (a miss).
- `by`: who adjudicated; `note`: one or two sentences. Set `filled` to true when the case is done.
- Fill `adjudication.json`; the Markdown files are for reading.
"""


def first_reachable_entries(v: dict[str, Any] | None, on_rule_table: bool = False) -> list[dict[str, Any]]:
    """REACHABLE entries (or, with `on_rule_table`, entries the rule table made REACHABLE), deciding first."""
    out = []
    for e in (v or {}).get("per_symbol") or []:
        if on_rule_table and e.get("pre_feasibility_result") == "REACHABLE":
            out.append(e)
        elif not on_rule_table and e.get("result") == "REACHABLE" and e.get("verified_path"):
            out.append(e)
    return sorted(out, key=lambda e: not e.get("decides_verdict", True))


def path_md(p: dict[str, Any], row: dict[str, Any], roots: dict[str, Path], go_version: str | None) -> list[str]:
    out = []
    for j, e in enumerate(p["edges"], start=1):
        out += edge_md(j, e, row, roots, go_version)
    return out


def edge_md(j: Any, e: dict[str, Any], row: dict[str, Any], roots: dict[str, Path], go_version: str | None) -> list[str]:
    cs = e.get("call_site") if (e.get("call_site") or {}).get("file") else {}
    head = f"{j}. {s7.code_span(e['caller'])} calls {s7.code_span(e['callee'])} ({s7.md(e.get('kind'))})"
    if not cs:
        return [head + " (synthetic edge, no call site)"]
    link = s7.source_link(cs["file"], cs["line"], row["app_repo"], row["app_commit"], go_version)
    head += f" at {s7.code_span(cs['file'] + ':' + str(cs['line']))}" + (f" [source]({link})" if link else "")
    text = s7.read_lines(cs["file"], cs["line"], roots)
    return [head, "", s7.code_block(text) if text else "   (source not available)", ""]


def case_markdown(row: dict[str, Any], off: dict[str, Any], on: dict[str, Any] | None, roots: dict[str, Path],
                  go_version: str | None, summary: str | None) -> str:
    out = [f"## {s7.md(row['id'])}", ""]
    facts = [("advisory", s7.code_span(row["advisory"]) + (" " + s7.md(summary) if summary else "")),
             ("vulnerable module", s7.code_span(f"{row.get('module')}@{row.get('version_selected')}")),
             ("mode", s7.md(row.get("mode"))),
             ("verdict without the filter", f"**{s7.md(row['verdict_off'])}**"),
             ("verdict with the filter", f"**{s7.md(row['verdict_on'])}** "
                                         f"({s7.md(', '.join(row.get('reason_codes_on') or []) or 'no reason codes')})"),
             ("filter answers (REACHABLE entries)", s7.md(row.get("filter_statuses")))]
    out += [f"- {k}: {v}" for k, v in facts]
    a = first_reachable_entries(off)
    if a:
        e = a[0]
        out += ["", f"### Path A (without the filter): {s7.code_span(e['target']['package'] + '.' + e['target']['symbol'])} "
                    f"from {s7.code_span(e.get('main_package'))}", ""]
        out += path_md(e["verified_path"], row, roots, go_version)
    b = first_reachable_entries(on)
    if row["verdict_on"] == "REACHABLE" and b:
        e = b[0]
        same = a and e["verified_path"] == a[0]["verified_path"]
        out += ["", f"### Path B (the path that passed the filter): "
                    f"{s7.code_span(e['target']['package'] + '.' + e['target']['symbol'])}", ""]
        out += ["Same as path A."] if same else path_md(e["verified_path"], row, roots, go_version)
    elif row["verdict_on"] != "REACHABLE":
        out += ["", "### Infeasible steps reported by the filter", ""]
        for e in first_reachable_entries(on, on_rule_table=True)[:MAX_ENTRIES]:
            f = e.get("feasibility") or {}
            out += [f"Target {s7.code_span(e['target']['package'] + '.' + e['target']['symbol'])}: filter answer "
                    f"{s7.md(f.get('status'))}, {len(f.get('examined') or [])} shortest path(s) examined.", ""]
            for k, ex in enumerate((f.get("examined") or [])[:MAX_STEPS], start=1):
                st = ex.get("first_infeasible")
                if not st:
                    continue
                out += [f"Examined path {k} (length {ex['length']}), step {st['edge_index'] + 1}, pattern "
                        f"{s7.md(st['pattern'])}: {s7.md(st['reason'])}", ""]
                for c, ce in enumerate(st.get("context_edges") or [], start=1):
                    out += edge_md(f"context {c}", ce, row, roots, go_version)
                out += edge_md("step", st["edge"], row, roots, go_version)
    fields = ["adjudication_off"] + (["adjudication_on"] if row["verdict_on"] == "REACHABLE" else ["steps_correct"]) + \
        ["truth", "by", "note"]
    out += ["", "| field | value |", "|---|---|"] + [f"| {f} | |" for f in fields]
    return "\n".join(out) + "\n"


def sheet_cases(rows: list[dict[str, Any]], off: dict[str, dict], on: dict[str, dict]) -> list[dict[str, Any]]:
    cases = []
    for r in rows:
        if r["verdict_off"] != "REACHABLE" and r["verdict_on"] != "REACHABLE":
            continue
        a, b = first_reachable_entries(off.get(r["id"])), first_reachable_entries(on.get(r["id"]))
        same = bool(a and b and a[0]["verified_path"] == b[0]["verified_path"])
        c = {"id": r["id"], "app_repo": r["app_repo"], "advisory": r["advisory"], "verdict_off": r["verdict_off"],
             "verdict_on": r["verdict_on"], "reason_codes_on": r.get("reason_codes_on") or [],
             "downgraded_by_filter": r["downgraded_by_filter"], "adjudication_off": None,
             "adjudication_on": ("SAME_AS_OFF" if same else None) if r["verdict_on"] == "REACHABLE" else None,
             "steps_correct": None, "truth": None, "by": None, "note": None, "filled": False}
        if same:
            c["prefilled"] = "adjudication_on = SAME_AS_OFF by code: path B is path A"
        cases.append(c)
    return cases


def build(results_dir: Path, roots_for: Any, go_version: str | None, summaries: dict[str, str]) -> dict[str, Any]:
    """Writes `adjudication/<app>.md` and `adjudication/adjudication.json` under `results_dir` (D3b)."""
    doc = json.loads((results_dir / "d3b_feasibility.json").read_text(encoding="utf-8"))
    off = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (results_dir / "verdicts_off").glob("*.json")}
    on = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (results_dir / "verdicts_on").glob("*.json")}
    cases = sheet_cases(doc["rows"], off, on)
    ids = {c["id"] for c in cases}
    by_app: dict[str, list[dict[str, Any]]] = {}
    for r in doc["rows"]:
        if r["id"] in ids:
            by_app.setdefault(r["app_repo"], []).append(r)
    adj = results_dir / "adjudication"
    adj.mkdir(parents=True, exist_ok=True)
    for app, rows in sorted(by_app.items()):
        head = [f"# CP9 adjudication (D3b, held-out): {s7.md(app)}", "",
                f"- application: {s7.code_span(app)} at tag {s7.code_span(rows[0].get('app_tag'))}, commit "
                f"{s7.code_span(rows[0].get('app_commit'))}",
                f"- cases to adjudicate: {len(rows)} (every case REACHABLE in either run)", "", INSTRUCTIONS]
        body = [case_markdown(r, off.get(r["id"]) or {}, on.get(r["id"]), roots_for(r), go_version,
                              summaries.get(r["advisory"])) for r in rows]
        (adj / s7.app_file_name(app)).write_text("\n".join(head) + "\n" + "\n".join(body), encoding="utf-8")
    sheet = {"schema_version": SCHEMA_VERSION, "set": "d3b", "allowed_adjudications": list(ADJUDICATIONS),
             "allowed_adjudications_on": list(ON_ADJUDICATIONS), "allowed_steps_correct": list(STEP_JUDGEMENTS),
             "allowed_truth": list(TRUTHS), "instructions": INSTRUCTIONS,
             "rule": "every D3b case whose verdict is REACHABLE with or without the filter", "cases": cases}
    (adj / "adjudication.json").write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")
    return sheet


def validate(sheet: dict[str, Any]) -> list[str]:
    """Problems of a filled sheet (empty list: ready to score)."""
    probs = []
    for c in sheet["cases"]:
        if not c.get("filled"):
            continue
        if c.get("adjudication_off") not in ADJUDICATIONS:
            probs.append(f"{c['id']}: adjudication_off {c.get('adjudication_off')!r}")
        if c["verdict_on"] == "REACHABLE" and c.get("adjudication_on") not in ON_ADJUDICATIONS:
            probs.append(f"{c['id']}: adjudication_on {c.get('adjudication_on')!r}")
        if c["downgraded_by_filter"] and c.get("steps_correct") not in STEP_JUDGEMENTS:
            probs.append(f"{c['id']}: steps_correct {c.get('steps_correct')!r}")
        if c.get("truth") not in TRUTHS:
            probs.append(f"{c['id']}: truth {c.get('truth')!r}")
        if not c.get("by"):
            probs.append(f"{c['id']}: by is empty")
    return probs
