"""`python -m vulntrace d3 sheet` (CP7b deliverable 4): the adjudication sheets.

One Markdown file per application and one JSON file with blank fields, under
`docs/results/cp7b/adjudication/`. Every per-case value in a sheet is copied from the verdict file
or read from the analysed source files; the only prose is the fixed instruction text, identical for
every case (no verdict text is invented). Advisory text and code are untrusted: in Markdown they
are escaped or put in fenced blocks whose fence is longer than any backtick run they contain.

Which cases are adjudicated (fixed before results, `SAMPLE_RULE`): every `REACHABLE` case; of
`NOT_REACHABLE` and of `CANT_DETERMINE` cases, all if there are at most `SAMPLE_SIZE`, otherwise
`SAMPLE_SIZE` in ascending order of sha256("<seed>:<case id>").
"""

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SEED = 20261028
SAMPLE_SIZE = 5
SAMPLE_RULE = ("All REACHABLE cases. Of NOT_REACHABLE and of CANT_DETERMINE cases: all if there are at most 5, "
               "otherwise 5 in ascending order of sha256(\"20261028:\" + case id).")
ADJUDICATIONS = ("CORRECT", "INFEASIBLE_PATH", "WRONG", "CANNOT_JUDGE")
TRUTHS = ("REACHABLE", "NOT_REACHABLE", "UNKNOWN")
MAX_PATHS_PER_CASE = 3
CONTEXT_LINES = 1

INSTRUCTIONS = """How to adjudicate (the same text for every case):

- Judge the **reachability claim**, not exploitability. `REACHABLE` means a call path from a `main` package to the
  target function exists in the call graph.
- `adjudication` is one of `CORRECT`, `INFEASIBLE_PATH`, `WRONG`, `CANNOT_JUDGE`.
  - `REACHABLE`: `CORRECT` if every step of the path below is a real call that can run in the application;
    `INFEASIBLE_PATH` if the calls exist but the path cannot run (for example a dynamic call that never takes this
    target, or code behind a condition that is never true); `WRONG` if a step does not exist or does not call the next
    function; `CANNOT_JUDGE` otherwise. If the case has more than one reachable target, judge the first path shown.
  - `NOT_REACHABLE`: `CORRECT` if, reading the code, none of the listed targets can be called from the application's
    `main` packages; `WRONG` if one can (a false NOT_REACHABLE: please say which in `note`).
  - `CANT_DETERMINE`: `CORRECT` if abstaining is reasonable (the answer is not clear from the code either); `WRONG`
    if reading the code gives a clear answer.
- `truth` (optional, NOT_REACHABLE and CANT_DETERMINE only): `REACHABLE`, `NOT_REACHABLE` or `UNKNOWN`, what reading
  the code says.
- `by`: who adjudicated (for example `owner` or `supervisor`). `note`: one or two sentences.
- Fill `adjudication.json`; the Markdown files are for reading. govulncheck is shown as a reference, not as truth.
"""


# --- the sample ------------------------------------------------------------------------------------
def _seeded(case_id: str) -> str:
    return hashlib.sha256(f"{SEED}:{case_id}".encode("utf-8")).hexdigest()


def sample(rows: list[dict[str, Any]]) -> dict[str, str]:
    """{case id: why it is adjudicated} for the cases the rule selects."""
    out: dict[str, str] = {}
    by_verdict: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r.get("verdict"):
            by_verdict[r["verdict"]].append(r["id"])
    for cid in by_verdict.get("REACHABLE", []):
        out[cid] = "every REACHABLE case"
    for verdict in ("NOT_REACHABLE", "CANT_DETERMINE"):
        ids = sorted(by_verdict.get(verdict, []), key=_seeded)
        if len(ids) <= SAMPLE_SIZE:
            out.update({cid: f"all {len(ids)} {verdict} cases" for cid in ids})
        else:
            out.update({cid: f"{SAMPLE_SIZE} of {len(ids)} {verdict} cases (seeded order)" for cid in ids[:SAMPLE_SIZE]})
    return out


# --- Markdown safety -------------------------------------------------------------------------------
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~>])")


def md(text: Any) -> str:
    """Escape untrusted text for Markdown prose (no links, images, HTML or emphasis can form)."""
    s = "" if text is None else str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = " ".join(s.split())
    return _MD_SPECIAL.sub(r"\\\1", s)


def code_span(text: Any) -> str:
    s = "" if text is None else " ".join(str(text).split())
    longest = max((len(m) for m in re.findall(r"`+", s)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if s.startswith("`") or s.endswith("`") or not s else ""
    return f"{fence}{pad}{s}{pad}{fence}"


def code_block(text: str, lang: str = "go") -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text.rstrip()}\n{fence}"


# --- source lines and links ------------------------------------------------------------------------
_MODCACHE = re.compile(r"^\$GOMODCACHE/(?P<mod>.+?)@(?P<ver>[^/]+)/(?P<rel>.+)$")
_PSEUDO = re.compile(r"-(?:\d{14})-([0-9a-f]{12})(?:\+incompatible)?$")


def _unescape_module(path: str) -> str:
    """Module cache paths escape capitals as `!x`."""
    return re.sub(r"!([a-z])", lambda m: m.group(1).upper(), path)


def source_link(file: str, line: int, app_repo: str, app_commit: str, go_version: str | None) -> str | None:
    """A best-effort browser link to the exact line; None when no stable URL is known. The code lines
    shown in the sheet are read from the analysed files and are authoritative; links are a convenience."""
    if file.startswith("$GOROOT/src/") and go_version:
        return f"https://github.com/golang/go/blob/{go_version}/{file[len('$GOROOT/'):]}#L{line}"
    m = _MODCACHE.match(file)
    if m:
        mod, ver, rel = _unescape_module(m.group("mod")), m.group("ver"), m.group("rel")
        pseudo = _PSEUDO.search(ver)
        ref = pseudo.group(1) if pseudo else ver.replace("+incompatible", "")
        parts = mod.split("/")
        if parts[0] == "github.com" and len(parts) >= 3:
            sub = "/".join(parts[3:])
            if sub and not re.fullmatch(r"v\d+", sub):
                ref = ref if pseudo else f"{sub}/{ref}"
                rel = f"{sub}/{rel}"
            return f"https://github.com/{parts[1]}/{parts[2]}/blob/{ref}/{rel}#L{line}"
        if parts[0] == "golang.org" and len(parts) == 3 and parts[1] == "x":
            return f"https://cs.opensource.google/go/x/{parts[2]}/+/{ref}:{rel};l={line}"
        return None
    if file.startswith("/") or file.startswith("$") or file.startswith("<"):
        return None
    return f"https://{app_repo}/blob/{app_commit}/{file}#L{line}"


def read_lines(file: str, line: int, roots: dict[str, Path], context: int = CONTEXT_LINES) -> str | None:
    """Lines line-context .. line+context of an analysed file; None if the file is not on disk.
    `roots`: {"app": tree, "$GOMODCACHE": module cache, "$GOROOT": goroot}."""
    if file.startswith("$GOMODCACHE/"):
        base, rel = roots.get("$GOMODCACHE"), file[len("$GOMODCACHE/"):]
    elif file.startswith("$GOROOT/"):
        base, rel = roots.get("$GOROOT"), file[len("$GOROOT/"):]
    elif file.startswith("/") or file.startswith("<"):
        return None
    else:
        base, rel = roots.get("app"), file
    if base is None:
        return None
    p = Path(base) / rel
    try:
        p.resolve().relative_to(Path(base).resolve())
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return None
    if not 1 <= line <= len(lines):
        return None
    lo, hi = max(1, line - context), min(len(lines), line + context)
    width = len(str(hi))
    return "\n".join(f"{n:>{width}}{'>' if n == line else ' '} {lines[n - 1]}" for n in range(lo, hi + 1))


# --- one case --------------------------------------------------------------------------------------
def _target(t: dict[str, Any]) -> str:
    return f"{t.get('package')}.{t.get('symbol')}"


def _context_only(v: dict[str, Any]) -> dict[str, Any]:
    return {_target(s): s.get("context_only") for s in v.get("symbols") or []}


def reachable_paths(v: dict[str, Any]) -> list[dict[str, Any]]:
    """First verified path per REACHABLE target: deciding entries first, then targets the fix really
    changed before context-only ones (Mode 1 keeps a function that only touched diff context, flagged
    `context_only`), otherwise in verdict order."""
    ctx = _context_only(v)
    seen, out = set(), []
    for e in sorted(v.get("per_symbol") or [], key=lambda e: (not e.get("decides_verdict", True),
                                                              ctx.get(_target(e["target"])) is True)):
        if e.get("result") != "REACHABLE" or not e.get("verified_path"):
            continue
        key = _target(e["target"])
        if key not in seen:
            seen.add(key)
            out.append({"target": key, "main": e.get("main_package"), "origin": e.get("origin"), "rank": e.get("rank"),
                        "context_only": ctx.get(key), "path": e["verified_path"]})
    return out


def only_context_reachable(v: dict[str, Any]) -> bool:
    """A REACHABLE verdict whose every reachable deciding target is context-only (no changed line)."""
    paths = [p for p in reachable_paths(v)]
    return bool(paths) and all(p["context_only"] is True for p in paths)


def case_markdown(row: dict[str, Any], v: dict[str, Any] | None, reason: str | None, roots: dict[str, Path],
                  go_version: str | None, summary: str | None = None) -> str:
    """`summary`: the advisory's summary from the pinned vulndb snapshot (copied, escaped)."""
    out = [f"## {md(row['id'])}", ""]
    adv = (v or {}).get("advisory") or {}
    summary = adv.get("summary") or summary
    facts = [("advisory", code_span(row["advisory"]) + (" " + md(summary) if summary else "")),
             ("vulnerable module", code_span(f"{row.get('module')}@{row.get('version_selected')}")),
             ("verdict", f"**{md(row.get('verdict'))}**"),
             ("reason codes", md(", ".join(row.get("reason_codes") or [])) or "none"),
             ("mode", md(row.get("mode"))), ("evidence level", md(row.get("evidence_level"))),
             ("symbols analysed", md(row.get("symbols"))), ("per-symbol results", md(row.get("entries"))),
             ("verifier", md((row.get("verification") or {}).get("status"))),
             ("adjudicate", md(reason) if reason else "not in the sample")]
    g = row.get("govulncheck")
    if g:
        facts.append(("govulncheck (reference, not truth)",
                      md(f"{g.get('verdict')} (finding level {g.get('level')})") +
                      (" via " + code_span(" -> ".join(reversed(g["trace"]))) if g.get("trace") else "")))
    out += [f"- {k}: {val}" for k, val in facts]
    if v is None:
        out += ["", "No verdict file (the case was not triaged)."]
    elif row.get("verdict") == "REACHABLE":
        paths = reachable_paths(v)
        out += ["", f"Reachable targets ({len(paths)}): " + ", ".join(
            code_span(p["target"]) + (" (context only)" if p["context_only"] is True else "") for p in paths)]
        for i, p in enumerate(paths[:MAX_PATHS_PER_CASE], start=1):
            out += ["", f"### Path {i}: {code_span(p['target'])} from {code_span(p['main'])}", "",
                    f"Target context only (no line of it changed in the fix, it touched diff context): "
                    f"{md(p['context_only'])}", ""]
            for j, e in enumerate(p["path"]["edges"], start=1):
                cs = e.get("call_site") if (e.get("call_site") or {}).get("file") else {}   # Go's synthetic edges have none
                head = f"{j}. {code_span(e['caller'])} calls {code_span(e['callee'])} ({md(e.get('kind'))})"
                if cs:
                    link = source_link(cs["file"], cs["line"], row["app_repo"], row["app_commit"], go_version)
                    loc = code_span(f"{cs['file']}:{cs['line']}")
                    head += f" at {loc}" + (f" [source]({link})" if link else "")
                    out.append(head)
                    text = read_lines(cs["file"], cs["line"], roots)
                    out += ["", code_block(text) if text else "   (source not available)", ""]
                else:
                    out.append(head + " (synthetic edge, no call site)")
        if len(paths) > MAX_PATHS_PER_CASE:
            out.append(f"\n{len(paths) - MAX_PATHS_PER_CASE} more reachable target(s); see the verdict file.")
    else:
        entries = v.get("per_symbol") or []
        targets = sorted({_target(e["target"]) for e in entries})
        out += ["", f"Targets analysed ({len(targets)}): " + (", ".join(code_span(t) for t in targets[:20]) or "none")]
        if len(targets) > 20:
            out.append(f"and {len(targets) - 20} more (see the verdict file).")
        pairs = defaultdict(int)
        for e in entries:
            m = e.get("methods") or {}
            pairs[(e.get("result"), e.get("reason_code"), m.get("CALLGRAPH_VTA"), m.get("LINKER_PRESENCE"))] += 1
        if pairs:
            out += ["", "| result | reason | call graph | linker | entries |", "|---|---|---|---|---|"]
            out += [f"| {md(a)} | {md(b)} | {md(c)} | {md(d)} | {n} |" for (a, b, c, d), n in sorted(pairs.items(), key=str)]
        nc = (v.get("coverage") or {}).get("not_covered") or []
        if nc:
            out.append("\nNot covered: " + ", ".join(f"{code_span(n.get('symbol'))} ({md(n.get('reason'))})" for n in nc[:10]))
        err = row.get("first_method_error") or row.get("app_list_error")
        if err:
            out.append("\nFirst error: " + code_span(err))
    out += ["", "| field | value |", "|---|---|", "| adjudication | |", "| by | |", "| note | |"]
    if row.get("verdict") in ("NOT_REACHABLE", "CANT_DETERMINE"):
        out.append("| truth | |")
    return "\n".join(out) + "\n"


def app_markdown(app_repo: str, rows: list[dict[str, Any]], verdicts: dict[str, dict], reasons: dict[str, str],
                 roots: dict[str, Path], go_version: str | None, selection: dict[str, Any] | None,
                 summaries: dict[str, str] | None = None) -> str:
    first = rows[0]
    head = [f"# Adjudication: {md(app_repo)}", "",
            f"- application: {code_span(app_repo)} at tag {code_span(first.get('app_tag'))}, commit "
            f"{code_span(first.get('app_commit'))}",
            f"- cases: {len(rows)}; to adjudicate: {sum(1 for r in rows if r['id'] in reasons)}",
            f"- sample rule: {md(SAMPLE_RULE)}"]
    if selection:
        head.append(f"- main packages analysed: " + ", ".join(code_span(m) for m in selection.get("mains") or []))
    head += ["", INSTRUCTIONS]
    body = [case_markdown(r, verdicts.get(r["id"]), reasons.get(r["id"]), roots, go_version,
                          (summaries or {}).get(r["advisory"])) for r in rows]
    return "\n".join(head) + "\n" + "\n".join(body)


def sheet_json(rows: list[dict[str, Any]], reasons: dict[str, str]) -> dict[str, Any]:
    cases = []
    for r in rows:
        c = {"id": r["id"], "app_repo": r["app_repo"], "advisory": r["advisory"], "verdict": r.get("verdict"),
             "reason_codes": r.get("reason_codes") or [], "mode": r.get("mode"),
             "adjudicate": r["id"] in reasons, "sample_reason": reasons.get(r["id"]),
             "adjudication": None, "by": None, "note": None}
        if r.get("verdict") in ("NOT_REACHABLE", "CANT_DETERMINE"):
            c["truth"] = None
        cases.append(c)
    return {"schema_version": SCHEMA_VERSION, "sample_rule": SAMPLE_RULE, "allowed_adjudications": list(ADJUDICATIONS),
            "allowed_truth": list(TRUTHS), "instructions": INSTRUCTIONS, "cases": cases}


def app_file_name(app_repo: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", app_repo.split("/", 1)[-1]) + ".md"
