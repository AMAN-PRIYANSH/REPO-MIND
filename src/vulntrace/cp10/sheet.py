"""`python -m vulntrace cp10 sheet` (CP10 deliverable 4): verdict-level adjudication sheets.

Same format family as CP7b and CP9: one Markdown file per application to read, and one JSON file
with blank fields to fill (`docs/results/cp10/adjudication/adjudication.json`). Every per-case
value is copied from the committed result files or read from the analysed source; the only prose
is the fixed instruction text below, identical for every case. Advisory text and code are
untrusted and are escaped or fenced (`d3.sheet.md`, `code_span`, `code_block`).

Items (fixed before any D3c result, `ITEM_RULE`):
- D3c: **every case**: `truth` and, when the CP10 (hygiene) verdict is REACHABLE, the judgement of
  the route shown (`path_judgement`).
- Truth-only items for the earlier sets where verdict-level truth is missing: the D3 (CP7b) cases
  whose verdict was REACHABLE (CP7b judged only their path) and the D3b (CP9) cases whose verdict
  was not REACHABLE (CP9 adjudicated only REACHABLE cases).

The truth question is the same for every item: is **any decision target** listed on the sheet
reachable from a `main` package of the application by some route? The decision targets are the
CP10 hygiene targets: the advisory's curated vulndb symbols (stratum S) or, without them, the
fix's changed non-test functions that are not context-only (stratum N). The same truth scores
VulnTrace (hygiene and legacy targets) and govulncheck.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from vulntrace.d3.sheet import app_file_name, code_block, code_span, md, read_lines, source_link
from vulntrace.paths import REPO_ROOT

SCHEMA_VERSION = "1.0"
RESULTS = REPO_ROOT / "docs" / "results" / "cp10"
TRUTHS = ("REACHABLE", "NOT_REACHABLE", "UNKNOWN")
PATH_JUDGEMENTS = ("CORRECT", "INFEASIBLE_PATH", "WRONG", "CANNOT_JUDGE")
CONFIDENCE = ("HIGH", "LOW")
MAX_TARGETS_SHOWN = 30
ITEM_RULE = ("D3c: every case (truth; plus the route judgement when the CP10 verdict is REACHABLE). Truth-only: the "
             "D3 (CP7b) cases whose verdict was REACHABLE and the D3b (CP9) cases whose verdict was not REACHABLE.")

INSTRUCTIONS = """How to adjudicate (the same text for every item):

- Judge **reachability**, never exploitability.
- `truth`: is **any decision target listed for the item** reachable from a `main` package of the application, by any
  route at all (not only the one shown)? `REACHABLE` (give one route in `route`, as `file:line` steps or a short
  description), `NOT_REACHABLE` (none can be called; say why in `note`), or `UNKNOWN` (the code does not settle it, for
  example run-time configuration decides). The decision targets are the CP10 hygiene targets: the advisory's curated
  vulndb symbols (stratum S) or, without them, the functions the fix changed whose own lines changed (stratum N).
- `confidence`: `HIGH` or `LOW`, how sure the `truth` answer is.
- `path_judgement` (only where asked: the CP10 verdict is REACHABLE): the route shown below. `CORRECT` if every step is a
  real call that can run in the application; `INFEASIBLE_PATH` if the calls exist but this route cannot run; `WRONG` if a
  step does not exist or does not call the next function; `CANNOT_JUDGE` otherwise. Steps marked unconfirmed are dynamic
  calls (interface method, function value, closure through a parameter) that the call graph could not confirm.
- `by`: who adjudicated. `note`: one or two sentences.
- Verdicts of VulnTrace (with hygiene and with legacy targets) and of govulncheck are shown for reference; none of them
  is truth. Fill `adjudication.json`; the Markdown files are for reading.
"""


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _target(t: dict[str, Any]) -> str:
    return f"{t.get('package')}.{t.get('symbol')}"


def decision_targets(v: dict[str, Any] | None, vcase: dict[str, Any] | None, module: str, stratum: str | None) -> list[str]:
    """The targets the truth question is about: stratum S, the advisory's curated vulndb symbols for the
    module (whatever mode the verdict used); otherwise the deciding targets of the CP10 hygiene verdict
    (Mode 1: the changed non-test functions that are not context-only)."""
    from vulntrace.pipeline import symbols as sy

    if stratum == "S":
        return [_target(t) for t in sy.curated_symbols(vcase, module)]
    if not v:
        return []
    return [_target(s) for s in v.get("symbols") or [] if s.get("decides_verdict", True) and s.get("origin") != "LIFTED"]


def shown_route(v: dict[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(entry, path_evidence) of the verdict's headline route (`path_evidence.entry`)."""
    pe = (v or {}).get("path_evidence") or {}
    ent = pe.get("entry")
    if not ent:
        return None, None
    for e in v.get("per_symbol") or []:
        if e["target"] == ent["target"] and e.get("main_package") == ent["main_package"] and e.get("shown_path"):
            return e, pe
    return None, None


def _route_md(path: dict[str, Any], row: dict[str, Any], roots: dict[str, Path | None], go_version: str | None,
              app_commit: str | None) -> list[str]:
    out = []
    for j, e in enumerate(path["edges"], start=1):
        cs = e.get("call_site") if (e.get("call_site") or {}).get("file") else {}
        kind = md(e.get("kind")) if e.get("kind") != "DYNAMIC" else \
            f"DYNAMIC {md(e.get('dynamic_kind'))}, **unconfirmed**"
        head = f"{j}. {code_span(e['caller'])} calls {code_span(e['callee'])} ({kind})"
        if cs:
            link = source_link(cs["file"], cs["line"], row["app_repo"], app_commit or "", go_version)
            head += f" at {code_span(cs['file'] + ':' + str(cs['line']))}" + (f" [source]({link})" if link else "")
            out.append(head)
            text = read_lines(cs["file"], cs["line"], roots)
            out += ["", code_block(text) if text else "   (source not available)", ""]
        else:
            out.append(head + " (synthetic edge, no call site)")
    return out


def item_markdown(item: dict[str, Any], row: dict[str, Any], v: dict[str, Any] | None, roots, go_version,
                  app_commit, summary: str | None) -> str:
    out = [f"## {md(item['id'])}", ""]
    g = row.get("govulncheck") or {}
    facts = [("item", md(item["kind"])), ("advisory", code_span(item["advisory"]) + (" " + md(summary) if summary else "")),
             ("vulnerable module", code_span(f"{row.get('module')}@{row.get('version_selected')}")),
             ("stratum", md(item.get("stratum")) + (" (curated vulndb symbols)" if item.get("stratum") == "S" else
                                                    " (no curated vulndb symbols)" if item.get("stratum") == "N" else "")),
             ("review status", md(row.get("review_status"))),
             ("VulnTrace, CP10 target hygiene", f"**{md(item.get('verdict_hygiene'))}** "
                                                f"{md(', '.join(item.get('reason_codes_hygiene') or []))}"),
             ("VulnTrace, legacy targets", f"**{md(item.get('verdict_legacy'))}** "
                                           f"{md(', '.join(item.get('reason_codes_legacy') or []))}"),
             ("govulncheck (reference, not truth)",
              md(f"{g.get('verdict')} at level {g.get('level')}; scored as {g.get('claim')}") if g else "not run"
              + "")]
    if g.get("symbols"):
        facts.append(("govulncheck symbols called", ", ".join(code_span(s) for s in g["symbols"][:10])))
    if g.get("trace"):
        facts.append(("govulncheck trace", code_span(" -> ".join(reversed(g["trace"])))))
    out += [f"- {k}: {val}" for k, val in facts]
    targets = item["decision_targets"]
    out += ["", f"Decision targets ({len(targets)}): " +
            (", ".join(code_span(t) for t in targets[:MAX_TARGETS_SHOWN]) or "none")]
    if len(targets) > MAX_TARGETS_SHOWN:
        out.append(f"and {len(targets) - MAX_TARGETS_SHOWN} more (see the verdict file).")
    if v is not None:
        extra = sorted({_target(s) for s in v.get("symbols") or [] if s.get("extra_reason")})
        if extra:
            out.append("Extra evidence only (never decide): " + ", ".join(code_span(t) for t in extra[:15]) +
                       (f" and {len(extra) - 15} more" if len(extra) > 15 else ""))
        res = Counter((e["result"], e.get("decides_verdict", True)) for e in v.get("per_symbol") or [])
        out.append("Per-entry results (result, deciding): " + md(dict(sorted(res.items(), key=str))))
    e, pe = shown_route(v)
    if item.get("path_judgement_asked") and e is not None:
        out += ["", f"### Route shown: {code_span(_target(e['target']))} from {code_span(e.get('main_package'))}", "",
                f"Evidence level {md(pe.get('evidence_level'))}, dynamic steps {md(pe.get('dynamic_steps'))}, passes the "
                f"CP9 filter {md(pe.get('passes_filter'))}. Route shown is an example from the call graph; steps marked "
                "unconfirmed may not run in this context.", ""]
        out += _route_md(e["shown_path"], row, roots, go_version, app_commit)
    fields = ["truth", "confidence", "route"] + (["path_judgement"] if item.get("path_judgement_asked") else []) + \
             ["by", "note"]
    out += ["", "| field | value |", "|---|---|"] + [f"| {f} | |" for f in fields]
    return "\n".join(out) + "\n"


def d3c_items(doc: dict[str, Any], verdicts: dict[str, dict], vcases: dict[str, dict]) -> list[dict[str, Any]]:
    items = []
    for r in doc["rows"]:
        v = verdicts.get(r["id"])
        h = r["hygiene"]
        items.append({"id": r["id"], "set": "d3c", "kind": "D3c case", "app_repo": r["app_repo"], "advisory": r["advisory"],
                      "module": r["module"], "stratum": r["stratum"],
                      "decision_targets": decision_targets(v, vcases.get(r["advisory"]), r["module"], r["stratum"]),
                      "verdict_hygiene": h["verdict"], "reason_codes_hygiene": h["reason_codes"] or [],
                      "verdict_legacy": r["legacy"]["verdict"], "reason_codes_legacy": r["legacy"]["reason_codes"] or [],
                      "govulncheck_claim": (r.get("govulncheck") or {}).get("claim"),
                      "govulncheck_level": (r.get("govulncheck") or {}).get("level"),
                      "evidence_level": h.get("evidence_level"),
                      "path_judgement_asked": h["verdict"] == "REACHABLE"})
    return items


def truth_only_items(set_name: str, doc: dict[str, Any], verdicts: dict[str, dict], earlier: dict[str, dict],
                     vcases: dict[str, dict]) -> list[dict]:
    """`earlier`: {case id: earlier verdict string (CP7b for D3, CP9 filter on for D3b)}."""
    want = (lambda vd: vd == "REACHABLE") if set_name == "d3" else (lambda vd: vd != "REACHABLE")
    items = []
    for r in doc["rows"]:
        if r["id"] not in earlier or not want(earlier[r["id"]]):
            continue
        v = verdicts.get(r["id"])
        items.append({"id": r["id"], "set": set_name, "kind": f"truth only ({set_name.upper()}, in-sample)",
                      "app_repo": r["app_repo"], "advisory": r["advisory"], "module": r["module"], "stratum": r["stratum"],
                      "decision_targets": decision_targets(v, vcases.get(r["advisory"]), r["module"], r["stratum"]),
                      "earlier_verdict": earlier[r["id"]],
                      "verdict_hygiene": r["hygiene"]["verdict"], "reason_codes_hygiene": r["hygiene"]["reason_codes"] or [],
                      "verdict_legacy": r["legacy"]["verdict"], "reason_codes_legacy": r["legacy"]["reason_codes"] or [],
                      "govulncheck_claim": (r.get("govulncheck") or {}).get("claim"),
                      "govulncheck_level": (r.get("govulncheck") or {}).get("level"),
                      "path_judgement_asked": False})
    return items


def sheet_json(items: list[dict[str, Any]]) -> dict[str, Any]:
    cases = []
    for it in items:
        c = {**it, "truth": None, "confidence": None, "route": None, "by": None, "note": None, "filled": False}
        if it["path_judgement_asked"]:
            c["path_judgement"] = None
        cases.append(c)
    return {"schema_version": SCHEMA_VERSION, "rule": ITEM_RULE, "allowed_truth": list(TRUTHS),
            "allowed_path_judgements": list(PATH_JUDGEMENTS), "allowed_confidence": list(CONFIDENCE),
            "instructions": INSTRUCTIONS, "cases": cases}


def earlier_verdicts(set_name: str) -> dict[str, str]:
    if set_name == "d3":
        doc = _read(REPO_ROOT / "docs" / "results" / "cp7b" / "d3_triage.json")
        return {r["id"]: r["verdict"] for r in doc["rows"] if r.get("verdict")}
    doc = _read(REPO_ROOT / "docs" / "results" / "cp9" / "d3b" / "d3b_feasibility.json")
    return {r["id"]: r["verdict_on"] for r in doc["rows"] if r.get("verdict_on")}


def load_set(set_name: str) -> tuple[dict[str, Any] | None, dict[str, dict]]:
    from vulntrace.eval.feasibility_real import read_verdicts

    base = RESULTS / set_name
    p = base / f"{set_name}_verdicts.json"
    if not p.is_file():
        return None, {}
    return _read(p), read_verdicts(base / "verdicts_hygiene")


def cmd_sheet(args, write_result, log) -> int:
    from vulntrace.d3 import select as sl
    from vulntrace.d3 import triage_run as tr
    from vulntrace.dataset import datasets

    out_dir = Path(args.out) if args.out else RESULTS / "adjudication"
    existing = out_dir / "adjudication.json"
    if existing.is_file() and not args.force and any(c.get("filled") for c in _read(existing).get("cases", [])):
        log(f"error: {existing} already has answers; refusing to overwrite (use --force only if that is intended)")
        return 2
    sets = {s: load_set(s) for s in ("d3c", "d3", "d3b")}
    if sets["d3c"][0] is None:
        log("missing prerequisite: docs/results/cp10/d3c/d3c_verdicts.json (run `python -m vulntrace cp10 run --set d3c`)")
        return 3
    for s, (doc, _) in sets.items():
        if doc is not None and doc.get("partial_run"):
            log(f"error: the {s} results are a partial run (--only); sheets need the full run")
            return 2
    all_cases = datasets.load_all_cases()[0]
    if not all_cases:
        log("missing prerequisite: the pinned vulndb snapshot (curated symbols and summaries)")
        return 3
    vcases = {c["id"]: c for c in all_cases}
    items = d3c_items(*sets["d3c"], vcases)
    for s in ("d3", "d3b"):
        if sets[s][0] is None:
            log(f"note: no CP10 run of {s}; its truth-only items are left out")
            continue
        items += truth_only_items(s, sets[s][0], sets[s][1], earlier_verdicts(s), vcases)
    summaries = {c["id"]: c["summary"] for c in all_cases}
    if not summaries:
        log("note: no vulndb snapshot; sheets are written without advisory summaries")
    data_dir = Path(args.data_dir) if args.data_dir else REPO_ROOT / "data" / "cp10"
    from vulntrace.cp10.cli import _gomodcache

    gomodcache = _gomodcache(args)
    root = tr.goroot()
    case_docs = {s: {c["id"]: c for c in _read(_case_path(s))["cases"]} for s in ("d3c", "d3", "d3b")
                 if _case_path(s).is_file()}
    rows = {(s, r["id"]): r for s, (doc, _) in sets.items() if doc for r in doc["rows"]}
    by_file: dict[str, list[str]] = {}
    for it in items:
        case = case_docs[it["set"]][it["id"]]
        row = rows[(it["set"], it["id"])]
        v = sets[it["set"]][1].get(it["id"])
        go_version = (((v or {}).get("toolchain") or {}).get("helper") or {}).get("go_version")
        roots = {"app": sl.app_tree_dir(data_dir / it["set"] / "shared" / "apps", case["app_repo"], case["app_commit"]),
                 "$GOMODCACHE": gomodcache, "$GOROOT": Path(root) if root else None}
        name = f"{it['set']}__{app_file_name(case['app_repo'])}"
        by_file.setdefault(name, []).append(item_markdown(it, {**row, "app_repo": case["app_repo"]}, v, roots,
                                                          go_version, case["app_commit"], summaries.get(it["advisory"])))
    for name, parts in by_file.items():
        text = (f"# CP10 adjudication: {md(name[:-3])}\n\n- rule: {md(ITEM_RULE)}\n\n" + INSTRUCTIONS + "\n" +
                "\n".join(parts))
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        n = len(text.encode("utf-8"))
        if n > 512 * 1024:
            log(f"error: {path} is {n} bytes, over 512 KiB")
            return 1
        log(f"wrote {path} ({n} bytes)")
    write_result(existing, sheet_json(items))
    log(f"{len(items)} items: " + str(dict(Counter(i["kind"] for i in items))))
    return 0


def _case_path(set_name: str) -> Path:
    from vulntrace.cp10.run import case_paths

    return case_paths(set_name)
