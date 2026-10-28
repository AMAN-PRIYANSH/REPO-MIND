"""`python -m vulntrace demo build` (CP7b deliverable 6).

One static HTML file, generated from verdict JSON files: verdict, mode, symbols with origin and
rank, call paths with file and line, verifier checks, coverage and limitations. No server, no
network, no external assets, no scripts: CSS is inline and a Content-Security-Policy meta tag
(`default-src 'none'`) forbids loading anything else. Every value taken from a verdict is HTML
escaped, because advisory text, symbol names and file paths come from third parties (CLAUDE.md
section 8). Links are only in-page anchors built from a hash, never from verdict text.
"""

import hashlib
import html
import json
from pathlib import Path
from typing import Any

TITLE = "VulnTrace verdicts"
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'"

CSS = """
:root { --fg:#1d1d1f; --muted:#5b5b66; --bg:#ffffff; --panel:#f5f5f7; --line:#d9d9de;
        --reach:#a3271f; --notreach:#1f6f3a; --cd:#7a5a00; --code:#f0f0f3; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e8e8ec; --muted:#a3a3ad; --bg:#16161a; --panel:#1f1f24; --line:#34343c;
          --reach:#ff8a80; --notreach:#7ddc9a; --cd:#f0c766; --code:#24242a; } }
* { box-sizing: border-box; }
body { margin:0; padding:16px; background:var(--bg); color:var(--fg);
       font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: .2rem 0 .4rem; }
h2 { font-size: 1.2rem; margin: 2.2rem 0 .4rem; padding-top: 1rem; border-top: 1px solid var(--line); }
h3 { font-size: 1rem; margin: 1.2rem 0 .3rem; }
p, li { overflow-wrap: anywhere; }
.muted { color: var(--muted); }
.badge { display:inline-block; padding: .05rem .5rem; border-radius: 4px; font-weight: 600;
         border: 1px solid currentColor; font-size: .85rem; }
.REACHABLE { color: var(--reach); } .NOT_REACHABLE { color: var(--notreach); } .CANT_DETERMINE { color: var(--cd); }
.PASSED { color: var(--notreach); } .FAILED, .REJECTED { color: var(--reach); }
table { border-collapse: collapse; width: 100%; margin: .3rem 0; font-size: .9rem; }
th, td { border: 1px solid var(--line); padding: .25rem .45rem; text-align: left; vertical-align: top;
         overflow-wrap: anywhere; }
th { background: var(--panel); font-weight: 600; }
.wrap { overflow-x: auto; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .85rem;
              background: var(--code); padding: 0 .2rem; border-radius: 3px; overflow-wrap: anywhere; }
ol.path { padding-left: 1.4rem; margin: .3rem 0; }
ol.path li { margin: .15rem 0; }
.kind { font-size: .75rem; padding: 0 .3rem; border: 1px solid var(--line); border-radius: 3px; }
details { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: .4rem .7rem;
          margin: .5rem 0; }
summary { cursor: pointer; font-weight: 600; }
.note { background: var(--panel); border-left: 3px solid var(--line); padding: .4rem .7rem; margin: .5rem 0; }
nav ul { padding-left: 1.2rem; }
"""


def esc(value: Any) -> str:
    """HTML-escape any value (None prints as an em dash)."""
    if value is None:
        return "&#8212;"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return html.escape(str(value), quote=True)


def anchor(case_id: str, index: int) -> str:
    """An in-page anchor made from a hash, so no verdict text ever lands in an attribute unescaped."""
    return "v" + str(index) + "-" + hashlib.sha256(str(case_id).encode("utf-8")).hexdigest()[:10]


def _badge(verdict: Any) -> str:
    v = str(verdict) if verdict in ("REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE") else "CANT_DETERMINE"
    return f'<span class="badge {v}">{esc(verdict)}</span>'


def _kv_table(rows: list[tuple[str, Any]]) -> str:
    body = "".join(f"<tr><th>{esc(k)}</th><td>{v}</td></tr>" for k, v in rows)
    return f'<div class="wrap"><table>{body}</table></div>'


def _target(t: dict[str, Any] | None) -> str:
    if not t:
        return esc(None)
    return f"<code>{esc(t.get('package'))}.{esc(t.get('symbol'))}</code>"


def _path(p: dict[str, Any] | None) -> str:
    if not p:
        return '<p class="muted">no path</p>'
    items = [f"<li>entry {_target(p.get('entry'))}</li>"]
    for e in p.get("edges") or []:
        cs = e.get("call_site") or {}
        where = f"<code>{esc(cs.get('file'))}:{esc(cs.get('line'))}</code>" if cs else '<span class="muted">synthetic edge, no call site</span>'
        items.append(f"<li><code>{esc(e.get('caller'))}</code> calls <code>{esc(e.get('callee'))}</code> at {where} "
                     f'<span class="kind">{esc(e.get("kind"))}</span></li>')
    items.append(f"<li>target {_target(p.get('target'))}</li>")
    return '<ol class="path">' + "".join(items) + "</ol>"


def _symbols(v: dict[str, Any]) -> str:
    syms = v.get("symbols") or []
    if not syms:
        return '<p class="muted">No target symbols.</p>'
    head = "<tr><th>package</th><th>symbol</th><th>origin</th><th>rank</th><th>score</th><th>decides verdict</th><th>context only</th></tr>"
    rows = "".join(
        f"<tr><td><code>{esc(s.get('package'))}</code></td><td><code>{esc(s.get('symbol'))}</code></td>"
        f"<td>{esc(s.get('origin'))}</td><td>{esc(s.get('rank'))}</td>"
        f"<td>{esc(round(s['score'], 4) if isinstance(s.get('score'), (int, float)) else s.get('score'))}</td>"
        f"<td>{esc(s.get('decides_verdict'))}</td><td>{esc(s.get('context_only'))}</td></tr>" for s in syms)
    return f'<div class="wrap"><table>{head}{rows}</table></div>'


def _entries(v: dict[str, Any]) -> str:
    out = []
    entries = v.get("per_symbol") or []
    if not entries:
        return '<p class="muted">No symbol was analysed.</p>'
    order = {"REACHABLE": 0, "CANT_DETERMINE": 1, "NOT_REACHABLE": 2}
    for e in sorted(entries, key=lambda e: (order.get(e.get("result"), 3), str(e.get("target")))):
        methods = e.get("methods") or {}
        head = (f"{_badge(e.get('result'))} {_target(e.get('target'))} "
                f"<span class=\"muted\">from <code>{esc(e.get('main_package'))}</code></span>")
        rows = [("result", _badge(e.get("result"))), ("before the verifier", esc(e.get("pre_verifier_result"))),
                ("reason", esc(e.get("reason_code"))), ("origin", esc(e.get("origin"))), ("rank", esc(e.get("rank"))),
                ("call graph (VTA)", esc(methods.get("CALLGRAPH_VTA"))),
                ("linker presence", esc(methods.get("LINKER_PRESENCE"))),
                ("package not in program", esc(e.get("package_not_in_program"))),
                ("evidence level", esc(e.get("evidence_level")))]
        if e.get("method_errors"):
            rows.append(("method errors", esc(e.get("method_errors"))))
        body = _kv_table(rows)
        if e.get("verified_path"):
            body += "<h3>Verified call path</h3>" + _path(e["verified_path"])
        elif e.get("paths"):
            body += "<h3>Call path (not verified)</h3>" + _path(e["paths"][0])
        if e.get("verifier_failures"):
            body += "<h3>Verifier failures</h3><ul>" + "".join(
                f"<li>{esc(f.get('check'))}: {esc(f.get('reason'))}</li>" for f in e["verifier_failures"]) + "</ul>"
        out.append(f"<details{' open' if e.get('result') == 'REACHABLE' else ''}><summary>{head}</summary>{body}</details>")
    return "".join(out)


def _verification(v: dict[str, Any]) -> str:
    ver = v.get("verification") or {}
    by = ver.get("checks_by_kind") or {}
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(s.get('run'))}</td><td>{esc(s.get('failed'))}</td><td>{esc(s.get('skipped'))}</td></tr>"
                   for k, s in sorted(by.items()))
    status = str(ver.get("status"))
    html_ = (f"<p>Status <span class=\"badge {esc(status if status in ('PASSED', 'FAILED', 'REJECTED') else '')}\">"
             f"{esc(ver.get('status'))}</span>, {esc(ver.get('checks_run'))} checks, {esc(ver.get('downgraded', 0))} "
             f"downgraded. The verifier can only downgrade a result, never upgrade it.</p>")
    if rows:
        html_ += f'<div class="wrap"><table><tr><th>check</th><th>run</th><th>failed</th><th>skipped</th></tr>{rows}</table></div>'
    return html_


def _coverage(v: dict[str, Any]) -> str:
    cov = v.get("coverage") or {}
    nc = cov.get("not_covered") or []
    rows = [("complete", esc(cov.get("complete"))),
            ("main packages analysed", "<br>".join(f"<code>{esc(m)}</code>" for m in cov.get("main_packages") or []) or esc(None)),
            ("main packages skipped", esc(len(cov.get("main_packages_skipped") or []))),
            ("symbols analysed", esc(cov.get("symbols_analysed"))),
            ("not covered", esc(len(nc)) + (": " + ", ".join(f"<code>{esc(n.get('symbol'))}</code> ({esc(n.get('reason'))})"
                                                              for n in nc[:20]) if nc else "")),
            ("app load error", esc(cov.get("app_list_error")))]
    return _kv_table(rows)


def _retrieval(v: dict[str, Any]) -> str:
    r = v.get("retrieval")
    if not r:
        return ""
    return "<h3>Retrieval (Mode 2)</h3>" + _kv_table([
        ("retriever requested", esc(r.get("config_requested"))), ("retriever used", esc(r.get("config_used"))),
        ("fallback", esc(r.get("fallback"))), ("k", esc(r.get("k"))), ("candidates in range", esc(r.get("candidates_total")))])


def verdict_section(v: dict[str, Any], index: int) -> str:
    adv = v.get("advisory") or {}
    app = v.get("target_app") or {}
    ms = v.get("mode_selection") or {}
    tc = v.get("toolchain") or {}
    helper = tc.get("helper") or {}
    head = [("verdict", _badge(v.get("verdict"))),
            ("reason codes", esc(", ".join(v.get("reason_codes") or []) or None)),
            ("before the Mode 2 policy", esc(v.get("pre_policy_verdict"))),
            ("mode", esc(v.get("mode")) + (f" <span class=\"muted\">({esc(ms.get('reason'))}: {esc(ms.get('explanation'))})</span>"
                                           if ms else "")),
            ("evidence level", esc(v.get("evidence_level"))),
            ("advisory", f"<code>{esc(adv.get('id') or v.get('case_id'))}</code> {esc(adv.get('summary'))}"),
            ("vulnerable module", f"<code>{esc(adv.get('module'))}</code>"),
            ("application", f"<code>{esc(app.get('module'))}</code> at <code>{esc(app.get('commit'))}</code>"),
            ("toolchain", f"{esc(helper.get('go_version'))}, x/tools {esc(helper.get('x_tools_version'))}, "
                          f"{esc((tc.get('env') or {}))}")]
    return (f'<h2 id="{anchor(v.get("case_id"), index)}">{esc(v.get("case_id"))}</h2>'
            + f'<p class="note">{esc(v.get("statement"))}</p>' + _kv_table(head)
            + "<h3>Target symbols</h3>" + _symbols(v) + _retrieval(v)
            + "<h3>Per symbol and main package</h3>" + _entries(v)
            + "<h3>Evidence verifier</h3>" + _verification(v)
            + "<h3>Coverage</h3>" + _coverage(v)
            + "<h3>Limitations</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in v.get("limitations") or []) + "</ul>")


def build_page(verdicts: list[tuple[str, dict[str, Any]]]) -> str:
    """`verdicts`: (label, verdict) pairs; the label (usually the file name) is shown in the index."""
    nav = "".join(f'<li><a href="#{anchor(v.get("case_id"), i)}">{esc(v.get("case_id"))}</a> '
                  f'{_badge(v.get("verdict"))} <span class="muted">{esc(label)}</span></li>'
                  for i, (label, v) in enumerate(verdicts))
    sections = "".join(verdict_section(v, i) for i, (_, v) in enumerate(verdicts))
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="referrer" content="no-referrer">'
            f"<title>{esc(TITLE)}</title><style>{CSS}</style></head><body><main>"
            f"<h1>{esc(TITLE)}</h1>"
            '<p class="muted">Reachability only: a verdict says whether a call path from a <code>main</code> package to '
            "the vulnerable code exists in the call graph, never whether it is exploitable. Generated offline from verdict "
            "files; no data leaves this page.</p>"
            f"<nav><ul>{nav}</ul></nav>{sections}</main></body></html>\n")


def _is_verdict(obj: Any) -> bool:
    return isinstance(obj, dict) and "verdict" in obj and "per_symbol" in obj


def is_verdict_file(path: Path) -> bool:
    try:
        return _is_verdict(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def load_verdicts(paths: list[Path]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for p in paths:
        obj = json.loads(Path(p).read_text(encoding="utf-8"))
        if not _is_verdict(obj):
            raise ValueError(f"{p} is not a verdict JSON file")
        out.append((Path(p).name, obj))
    return out
