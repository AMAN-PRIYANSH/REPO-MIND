"""CP10 deliverable 2: evidence honesty (labels and the shown route; never changes a verdict).

CP7b and CP9 found that on real applications the route the system shows is usually not one that
can run (0/7 runnable on D3 and on D3b), mostly because of dynamic calls joined across contexts.
So the evidence says how sure it is:

- **Route shown.** For each REACHABLE entry the shown route (`shown_path`) is chosen among the
  paths that passed the evidence verifier: the filter's ranked path (CP9 search, the N examined
  paths, best by: passes the CP9 filter, then fewer DYNAMIC steps, then shorter), the filter's
  CP9 evidence path, and the call-graph method's own paths. The same order decides among them:
  a path known to pass the filter first, then fewer DYNAMIC steps, then shorter, then the order
  above. `verified_path` keeps its CP9 meaning, unchanged.
- **Labels.** Every DYNAMIC step of the shown route carries `confirmed: false` and its kind
  (`INTERFACE_METHOD`, `FUNCTION_VALUE`, `CLOSURE_VIA_PARAMETER`, from the helper; `UNKNOWN` when
  the helper was not asked). Each entry and the verdict record `path_evidence.evidence_level`:
  `STATIC_PATH` (no dynamic step) or `HAS_DYNAMIC_STEPS` (with their count). The verdict level is
  that of the best shown route among the deciding REACHABLE entries.
- **Statement.** The verdict, the text output and the demo page say plainly: "route shown is an
  example from the call graph; steps marked unconfirmed may not run in this context".

`label_verdict` is a pure function. It adds keys only (`shown_path`, `path_evidence`) and
`assert_labels_only` proves on every verdict that nothing else changed.
"""

import copy
from collections import Counter
from typing import Any

from vulntrace.verdict import REACHABLE

STATIC_PATH, HAS_DYNAMIC_STEPS, NO_ROUTE_SHOWN = "STATIC_PATH", "HAS_DYNAMIC_STEPS", "NO_ROUTE_SHOWN"
UNKNOWN_KIND = "UNKNOWN"
SRC_RANKED, SRC_FILTER_EVIDENCE, SRC_METHOD = "FILTER_RANKED_PATH", "FILTER_EVIDENCE_PATH", "METHOD_PATH"
ROUTE_STATEMENT = ("Route shown is an example from the call graph; steps marked unconfirmed may not run in this "
                   "context.")
RANK_ORDER = "passes the CP9 filter, then fewer DYNAMIC steps, then shorter"


def dynamic_steps(path: dict[str, Any] | None) -> int:
    return sum(1 for e in (path or {}).get("edges") or [] if e.get("kind") == "DYNAMIC")


def label_path(path: dict[str, Any]) -> dict[str, Any]:
    """A copy whose DYNAMIC edges carry `confirmed: false` and `dynamic_kind`."""
    p = copy.deepcopy(path)
    for e in p.get("edges") or []:
        if e.get("kind") == "DYNAMIC":
            e["confirmed"] = False
            e.setdefault("dynamic_kind", UNKNOWN_KIND)
    return p


def _candidates(e: dict[str, Any]) -> list[tuple[dict[str, Any], str, bool, int]]:
    """(path, source, passes the CP9 filter, source order) for every path of a REACHABLE entry that
    passed the verifier. Without `path_checks` (no ranking asked), only the verified path."""
    f = e.get("feasibility") or {}
    checks = e.get("path_checks")
    feasible = f.get("status") == "FEASIBLE"
    out: list[tuple[dict[str, Any], str, bool, int]] = []
    if checks is None:
        vp = e.get("verified_path")
        if vp is not None:
            src = SRC_FILTER_EVIDENCE if feasible and vp == f.get("evidence_path") else SRC_METHOD
            out.append((vp, src, feasible and vp == f.get("evidence_path"), 1))
        return out
    if feasible and f.get("ranked_path") and checks.get("ranked_path_passed"):
        out.append((f["ranked_path"], SRC_RANKED, True, 0))
    if feasible and f.get("evidence_path") and checks.get("evidence_path_passed"):
        out.append((f["evidence_path"], SRC_FILTER_EVIDENCE, True, 1))
    for pi in checks.get("method_paths_passed") or []:
        p = (e.get("paths") or [])[pi]
        known_pass = feasible and (p == f.get("evidence_path") or p == f.get("ranked_path"))
        out.append((p, SRC_METHOD, known_pass, 2 + pi))
    return out


def rank_key(c: tuple[dict[str, Any], str, bool, int]) -> tuple[int, int, int, int]:
    path, _, passes, order = c
    return (0 if passes else 1, dynamic_steps(path), len(path.get("edges") or []), order)


def entry_evidence(e: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """(shown path or None, path_evidence) of one entry."""
    f = e.get("feasibility") or {}
    examined = f.get("examined_total", len(f.get("examined") or [])) if f else None
    base = {"rank_order": RANK_ORDER, "examined_paths": examined, "max_examined_paths": f.get("max_examined_paths"),
            "filter_status": f.get("status")}
    if e.get("result") != REACHABLE:
        return None, {**base, "evidence_level": NO_ROUTE_SHOWN, "dynamic_steps": None, "candidates": 0}
    cands = _candidates(e)
    if not cands:
        return None, {**base, "evidence_level": NO_ROUTE_SHOWN, "dynamic_steps": None, "candidates": 0}
    best = min(cands, key=rank_key)
    path, src, passes, _ = best
    shown = label_path(path)
    n = dynamic_steps(path)
    kinds = Counter(ed.get("dynamic_kind", UNKNOWN_KIND) for ed in shown["edges"] if ed.get("kind") == "DYNAMIC")
    return shown, {**base, "evidence_level": HAS_DYNAMIC_STEPS if n else STATIC_PATH, "dynamic_steps": n,
                   "dynamic_kinds": dict(sorted(kinds.items())), "length": len(path.get("edges") or []),
                   "source": src, "passes_filter": passes, "candidates": len(cands),
                   "same_as_verified_path": path == e.get("verified_path")}


def label_verdict(v: dict[str, Any]) -> dict[str, Any]:
    """The verdict with CP10 evidence labels added (input not modified)."""
    out = copy.deepcopy(v)
    best: tuple[tuple, dict[str, Any], dict[str, Any]] | None = None
    for e in out.get("per_symbol") or []:
        shown, pe = entry_evidence(e)
        e["path_evidence"] = pe
        if shown is not None:
            e["shown_path"] = shown
            if e.get("decides_verdict", True):
                key = (0 if pe["passes_filter"] else 1, pe["dynamic_steps"], pe["length"])
                if best is None or key < best[0]:
                    best = (key, e, pe)
    if out.get("verdict") == REACHABLE and best is not None:
        _, e, pe = best
        out["path_evidence"] = {"evidence_level": pe["evidence_level"], "dynamic_steps": pe["dynamic_steps"],
                                "dynamic_kinds": pe["dynamic_kinds"], "length": pe["length"],
                                "passes_filter": pe["passes_filter"], "source": pe["source"],
                                "entry": {"target": e["target"], "main_package": e.get("main_package")},
                                "statement": ROUTE_STATEMENT}
    else:
        out["path_evidence"] = {"evidence_level": NO_ROUTE_SHOWN, "dynamic_steps": None, "statement": ROUTE_STATEMENT}
    assert_labels_only(v, out)
    return out


ADDED_ENTRY_KEYS = ("shown_path", "path_evidence")


def assert_labels_only(before: dict[str, Any], after: dict[str, Any]) -> None:
    """The evidence stage adds keys and nothing else."""
    b, a = copy.deepcopy(before), copy.deepcopy(after)
    a.pop("path_evidence", None)
    for e in a.get("per_symbol") or []:
        for k in ADDED_ENTRY_KEYS:
            e.pop(k, None)
    for e in b.get("per_symbol") or []:
        for k in ADDED_ENTRY_KEYS:
            e.pop(k, None)
    b.pop("path_evidence", None)
    if a != b:
        raise AssertionError("the evidence stage changed more than its own labels")


def strip_cp10_evidence(obj: Any) -> Any:
    """CP10's additive evidence keys removed (for comparing a CP10 run with a CP9 recording):
    `dynamic_kind`/`confirmed` on edges, `dynamic_steps` on examined paths, the filter's
    `rank_rule`/`ranked_path`/`ranked_index`, the entry's `path_checks`, `shown_path` and
    `path_evidence`, the verdict's `path_evidence` and the verifier's `display_checks_by_kind`."""
    drop = {"dynamic_kind", "confirmed", "dynamic_steps", "rank_rule", "ranked_path", "ranked_index", "path_checks",
            "shown_path", "path_evidence", "display_checks_by_kind"}
    if isinstance(obj, dict):
        return {k: strip_cp10_evidence(v) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [strip_cp10_evidence(x) for x in obj]
    return obj


def text_summary(v: dict[str, Any]) -> str:
    """The plain-text output of `triage --format text`: verdict, reasons, the shown route with each
    step's kind, and the route statement."""
    lines = [f"{v.get('case_id')}: {v.get('verdict')}" + (f" ({', '.join(v['reason_codes'])})" if v.get("reason_codes") else ""),
             v.get("statement", "")]
    tp = v.get("target_policy")
    if tp:
        lines.append(f"targets: stratum {tp['stratum']}, {tp['deciding_targets']} deciding, {tp['extra_targets']} extra")
    pe = v.get("path_evidence") or {}
    if v.get("verdict") == REACHABLE and pe.get("evidence_level") not in (None, NO_ROUTE_SHOWN):
        ent = pe["entry"]
        e = next((x for x in v["per_symbol"] if x["target"] == ent["target"] and x.get("main_package") == ent["main_package"]
                  and x.get("shown_path")), None)
        lines.append(f"evidence level: {pe['evidence_level']}" +
                     (f" ({pe['dynamic_steps']} dynamic step(s): {pe['dynamic_kinds']})" if pe["dynamic_steps"] else ""))
        lines.append(f"route shown to {ent['target']['package']}.{ent['target']['symbol']} from {ent['main_package']}:")
        for i, ed in enumerate((e or {}).get("shown_path", {}).get("edges") or [], start=1):
            cs = ed.get("call_site") or {}
            where = f"{cs.get('file')}:{cs.get('line')}" if cs.get("file") else "(synthetic edge)"
            tag = "STATIC" if ed.get("kind") != "DYNAMIC" else f"DYNAMIC {ed.get('dynamic_kind', UNKNOWN_KIND)}, unconfirmed"
            lines.append(f"  {i}. {ed.get('caller')} -> {ed.get('callee')} at {where} [{tag}]")
    lines.append(ROUTE_STATEMENT)
    return "\n".join(lines) + "\n"
