"""Scoring a filled D3 adjudication sheet (CP7b deliverable 5). Pure functions.

The sheet is checked against the triage results first: unknown values, a verdict that differs from
the triage file, or a sampled case left blank are errors, and nothing is scored until they are
fixed. Rates carry raw counts and a 95% Wilson interval. Cases of one application are not
independent and there are only five applications, so the intervals are a floor on the uncertainty,
not a full account of it; the per-application table is shown next to every rate.
"""

from collections import Counter, defaultdict
from typing import Any

from vulntrace.d3 import sheet as sh
from vulntrace.eval.triage_eval import wilson

REACHABLE, NOT_REACHABLE, CANT_DETERMINE = "REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE"


class SheetError(ValueError):
    pass


def validate(sheet: dict[str, Any], triage_doc: dict[str, Any]) -> list[str]:
    """Every problem that stops scoring (empty list: the sheet can be scored)."""
    errors = []
    rows = {r["id"]: r for r in triage_doc["rows"]}
    seen = set()
    for c in sheet.get("cases") or []:
        cid = c.get("id")
        if cid in seen:
            errors.append(f"{cid}: listed twice")
        seen.add(cid)
        row = rows.get(cid)
        if row is None:
            errors.append(f"{cid}: not in the triage results")
            continue
        if c.get("verdict") != row.get("verdict"):
            errors.append(f"{cid}: sheet verdict {c.get('verdict')} differs from the triage result {row.get('verdict')}")
        adj = c.get("adjudication")
        if adj is not None and adj not in sh.ADJUDICATIONS:
            errors.append(f"{cid}: adjudication {adj!r} is not one of {', '.join(sh.ADJUDICATIONS)}")
        if adj == "INFEASIBLE_PATH" and c.get("verdict") != REACHABLE:
            errors.append(f"{cid}: INFEASIBLE_PATH applies to REACHABLE verdicts only")
        if c.get("truth") is not None and c["truth"] not in sh.TRUTHS:
            errors.append(f"{cid}: truth {c['truth']!r} is not one of {', '.join(sh.TRUTHS)}")
        if c.get("adjudicate") and adj is None:
            errors.append(f"{cid}: in the sample but not adjudicated")
        if adj is not None and not (c.get("by") or "").strip():
            errors.append(f"{cid}: adjudicated without `by`")
    missing = set(rows) - seen
    errors += [f"{cid}: in the triage results but not in the sheet" for cid in sorted(missing)]
    return errors


def _rate(k: int, n: int) -> dict[str, Any]:
    w = wilson(k, n)
    return {"k": k, "n": n, "rate": w["rate"] if n else None, "ci_low": w["ci_low"] if n else None,
            "ci_high": w["ci_high"] if n else None}


def score(sheet: dict[str, Any], triage_doc: dict[str, Any]) -> dict[str, Any]:
    errors = validate(sheet, triage_doc)
    if errors:
        raise SheetError("; ".join(errors[:10]) + (f" (+{len(errors) - 10} more)" if len(errors) > 10 else ""))
    rows = {r["id"]: r for r in triage_doc["rows"]}
    adj = {c["id"]: c for c in sheet["cases"] if c.get("adjudication")}
    triaged = [r for r in rows.values() if r.get("verdict")]
    verdicts = Counter(r["verdict"] for r in triaged)

    def judged(verdict: str) -> list[dict[str, Any]]:
        return [adj[r["id"]] for r in triaged if r["verdict"] == verdict and r["id"] in adj]

    reach = judged(REACHABLE)
    rc = Counter(c["adjudication"] for c in reach)
    r_decided = rc["CORRECT"] + rc["INFEASIBLE_PATH"] + rc["WRONG"]
    nr = judged(NOT_REACHABLE)
    nc = Counter(c["adjudication"] for c in nr)
    cd = judged(CANT_DETERMINE)
    cc = Counter(c["adjudication"] for c in cd)
    per_app: dict[str, Counter] = defaultdict(Counter)
    for r in triaged:
        per_app[r["app_repo"]][r["verdict"]] += 1
        a = adj.get(r["id"])
        if a:
            per_app[r["app_repo"]][f"{r['verdict']}:{a['adjudication']}"] += 1
    gv_rows = [r for r in rows.values() if r.get("govulncheck")]
    gv_vs_adj = []
    for r in gv_rows:
        a = adj.get(r["id"])
        if a and r["govulncheck"]["agreement"] == "DISAGREE":
            gv_vs_adj.append({"id": r["id"], "ours": r["verdict"], "govulncheck": r["govulncheck"]["verdict"],
                              "adjudication": a["adjudication"], "truth": a.get("truth")})
    return {
        "cases": len(rows), "triaged": len(triaged), "not_triaged": len(rows) - len(triaged),
        "apps": len({r["app_repo"] for r in rows.values()}),
        "verdicts": {k: verdicts.get(k, 0) for k in (REACHABLE, NOT_REACHABLE, CANT_DETERMINE)},
        "answered": verdicts.get(REACHABLE, 0) + verdicts.get(NOT_REACHABLE, 0),
        "false_not_reachable": {"found": nc["WRONG"], "adjudicated": len(nr), "of_total": verdicts.get(NOT_REACHABLE, 0),
                                "cannot_judge": nc["CANNOT_JUDGE"], "ids": sorted(c["id"] for c in nr if c["adjudication"] == "WRONG")},
        "reachable": {"adjudicated": len(reach), "of_total": verdicts.get(REACHABLE, 0), "counts": dict(rc),
                      "precision": _rate(rc["CORRECT"], r_decided),
                      "path_exists_rate": _rate(rc["CORRECT"] + rc["INFEASIBLE_PATH"], r_decided),
                      "cannot_judge": rc["CANNOT_JUDGE"]},
        "not_reachable": {"adjudicated": len(nr), "counts": dict(nc),
                          "correct": _rate(nc["CORRECT"], nc["CORRECT"] + nc["WRONG"])},
        "cant_determine": {"share": _rate(verdicts.get(CANT_DETERMINE, 0), len(triaged)),
                           "reasons": dict(Counter("+".join(sorted(r.get("reason_codes") or [])) or "NONE"
                                                   for r in triaged if r["verdict"] == CANT_DETERMINE)),
                           "adjudicated": len(cd), "counts": dict(cc),
                           "truth": dict(Counter(c.get("truth") or "not given" for c in cd))},
        "govulncheck": {"compared": len(gv_rows), "agreement": dict(Counter(r["govulncheck"]["agreement"] for r in gv_rows)),
                        "agree_rate": _rate(sum(1 for r in gv_rows if r["govulncheck"]["agreement"] == "AGREE"),
                                            sum(1 for r in gv_rows if r["govulncheck"]["agreement"] in ("AGREE", "DISAGREE"))),
                        "disagreements_adjudicated": gv_vs_adj},
        "per_app": {a: dict(c) for a, c in sorted(per_app.items())},
        "adjudicated_by": dict(Counter((c.get("by") or "").strip() for c in adj.values())),
        "extra_adjudications": sorted(cid for cid, c in adj.items() if not c.get("adjudicate")),
    }


def pick_examples(sheet: dict[str, Any], triage_doc: dict[str, Any]) -> dict[str, str | None]:
    """Worked examples by a fixed rule (smallest case id in each group): a REACHABLE case judged
    CORRECT (else any REACHABLE), a CANT_DETERMINE case that was adjudicated (else any), and a
    govulncheck disagreement (else none)."""
    rows = sorted(triage_doc["rows"], key=lambda r: r["id"])
    adj = {c["id"]: c for c in sheet["cases"] if c.get("adjudication")}

    def first(pred):
        return next((r["id"] for r in rows if pred(r)), None)

    return {
        "reachable": first(lambda r: r.get("verdict") == REACHABLE and (adj.get(r["id"]) or {}).get("adjudication") == "CORRECT")
        or first(lambda r: r.get("verdict") == REACHABLE),
        "cant_determine": first(lambda r: r.get("verdict") == CANT_DETERMINE and r["id"] in adj)
        or first(lambda r: r.get("verdict") == CANT_DETERMINE),
        "disagreement": first(lambda r: (r.get("govulncheck") or {}).get("agreement") == "DISAGREE"),
    }
