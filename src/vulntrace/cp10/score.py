"""CP10 deliverable 5: verdict-level scoring against adjudicated truth (pure functions).

Tools: VulnTrace with the CP10 target hygiene (`hygiene`), VulnTrace with `--legacy-targets`
(`legacy`), and govulncheck (`govulncheck`, its claim as defined in `cp10.run.govulncheck_view`:
stratum S, REACHABLE only at symbol level; stratum N, any finding is its REACHABLE claim).

Per stratum (S, N) and overall, per tool:
- verdict precision of REACHABLE: truth REACHABLE among the tool's REACHABLE answers with known truth;
- false NOT_REACHABLE count (the dangerous error): truth REACHABLE but the tool said NOT_REACHABLE,
  reported even when 0, with the number of truth-REACHABLE cases;
- CANT_DETERMINE rate (govulncheck: a failed run);
- UNKNOWN truth count;
- 95% Wilson intervals and n everywhere. Cases of one application are not independent, so the
  intervals understate the uncertainty (said in the results document).
Plus the paired comparison of each VulnTrace variant with govulncheck on the same cases, path
precision split by the route's evidence level, and the hygiene changes (every hygiene-induced
NOT_REACHABLE in stratum S listed with its truth).
"""

from collections import Counter
from typing import Any

from vulntrace.eval.triage_eval import wilson

R, NR, CD, UNKNOWN = "REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE", "UNKNOWN"
TOOLS = ("hygiene", "legacy", "govulncheck")
STRATA = ("S", "N", "ALL")
JUDGED = ("CORRECT", "INFEASIBLE_PATH", "WRONG")


def tool_answer(row: dict[str, Any], tool: str) -> str | None:
    """REACHABLE / NOT_REACHABLE / CANT_DETERMINE, or None when the tool did not run on the case."""
    if tool == "govulncheck":
        g = row.get("govulncheck")
        if g is None:
            return None
        return g.get("claim") or CD           # a failed govulncheck run is an abstention
    return (row.get(tool) or {}).get("verdict")


def validate(sheet: dict[str, Any], d3c_doc: dict[str, Any]) -> list[str]:
    """Problems that stop scoring (an unfilled or malformed sheet)."""
    errors = []
    ids = {r["id"] for r in d3c_doc["rows"]}
    got = {c["id"] for c in sheet["cases"] if c["set"] == "d3c"}
    if ids != got:
        errors.append(f"the sheet's D3c cases differ from the results: missing {sorted(ids - got)}, extra {sorted(got - ids)}")
    for c in sheet["cases"]:
        if not c.get("filled"):
            errors.append(f"{c['set']}:{c['id']}: not filled")
            continue
        if c.get("truth") not in sheet["allowed_truth"]:
            errors.append(f"{c['set']}:{c['id']}: truth {c.get('truth')!r} not in {sheet['allowed_truth']}")
        if c.get("path_judgement_asked") and c.get("path_judgement") not in sheet["allowed_path_judgements"]:
            errors.append(f"{c['set']}:{c['id']}: path_judgement {c.get('path_judgement')!r} not allowed")
        if not c.get("by"):
            errors.append(f"{c['set']}:{c['id']}: `by` is empty")
    return errors


def _rate(k: int, n: int) -> dict[str, Any]:
    return wilson(k, n)


def tool_scores(rows: list[dict[str, Any]], truth: dict[str, str], tool: str) -> dict[str, Any]:
    ans = {r["id"]: tool_answer(r, tool) for r in rows}
    ran = [r["id"] for r in rows if ans[r["id"]] is not None]
    reach = [i for i in ran if ans[i] == R]
    reach_known = [i for i in reach if truth.get(i) in (R, NR)]
    notr = [i for i in ran if ans[i] == NR]
    notr_known = [i for i in notr if truth.get(i) in (R, NR)]
    truth_r = [i for i in ran if truth.get(i) == R]
    false_nr = [i for i in notr if truth.get(i) == R]
    false_r = [i for i in reach if truth.get(i) == NR]
    cd = [i for i in ran if ans[i] == CD]
    return {"cases": len(rows), "ran": len(ran), "answers": dict(Counter(ans[i] for i in ran)),
            "reachable_precision": _rate(sum(1 for i in reach_known if truth[i] == R), len(reach_known)),
            "reachable_unknown_truth": len(reach) - len(reach_known),
            "not_reachable_precision": _rate(sum(1 for i in notr_known if truth[i] == NR), len(notr_known)),
            "false_not_reachable": {"count": len(false_nr), "ids": false_nr, "truth_reachable_cases": len(truth_r),
                                    "rate": _rate(len(false_nr), len(truth_r))},
            "false_reachable": {"count": len(false_r), "ids": false_r},
            "cant_determine_rate": _rate(len(cd), len(ran)), "cant_determine_ids": cd,
            "truth_reachable_recall": _rate(sum(1 for i in truth_r if ans[i] == R), len(truth_r))}


def paired(rows: list[dict[str, Any]], truth: dict[str, str], a: str, b: str = "govulncheck") -> dict[str, Any]:
    """`a` vs `b` on the cases both answered (REACHABLE or NOT_REACHABLE)."""
    agree, disagree, one_abstained = [], [], []
    for r in rows:
        x, y = tool_answer(r, a), tool_answer(r, b)
        if x is None or y is None:
            continue
        if x not in (R, NR) or y not in (R, NR):
            if (x in (R, NR)) != (y in (R, NR)):
                one_abstained.append({"id": r["id"], a: x, b: y, "truth": truth.get(r["id"])})
            continue
        t = truth.get(r["id"])
        item = {"id": r["id"], a: x, b: y, "truth": t,
                "right": ("both" if x == t and y == t else a if x == t else b if y == t else
                          "neither" if t in (R, NR) else "unknown")}
        (agree if x == y else disagree).append(item)
    return {"pair": [a, b], "both_answered": len(agree) + len(disagree), "agree": len(agree),
            "agree_by_truth": dict(Counter(i["truth"] for i in agree)),
            "agree_both_wrong": [i["id"] for i in agree if i["right"] == "neither"],
            "disagree": disagree, "disagree_right": dict(Counter(i["right"] for i in disagree)),
            "one_abstained": one_abstained,
            "agreement_rate": _rate(len(agree), len(agree) + len(disagree))}


def path_precision(rows: list[dict[str, Any]], sheet_by_id: dict[str, dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for level in ("STATIC_PATH", "HAS_DYNAMIC_STEPS", "ALL"):
        js = [sheet_by_id[r["id"]].get("path_judgement") for r in rows
              if r["hygiene"]["verdict"] == R and r["id"] in sheet_by_id
              and (level == "ALL" or r["hygiene"].get("evidence_level") == level)]
        judged = [j for j in js if j in JUDGED]
        out[level] = {"routes": len(js), "judgements": dict(Counter(js)),
                      "precision": _rate(sum(1 for j in judged if j == "CORRECT"), len(judged)),
                      "cannot_judge": sum(1 for j in js if j == "CANNOT_JUDGE")}
    return out


def hygiene_changes(rows: list[dict[str, Any]], truth: dict[str, str]) -> list[dict[str, Any]]:
    return [{"id": r["id"], "stratum": r["stratum"], "legacy": r["legacy"]["verdict"],
             "legacy_reasons": r["legacy"]["reason_codes"], "hygiene": r["hygiene"]["verdict"],
             "hygiene_reasons": r["hygiene"]["reason_codes"], "made_not_reachable": r["hygiene_made_not_reachable"],
             "truth": truth.get(r["id"]),
             "hygiene_right": (r["hygiene"]["verdict"] == truth.get(r["id"])) if truth.get(r["id"]) in (R, NR) else None,
             "legacy_right": (r["legacy"]["verdict"] == truth.get(r["id"])) if truth.get(r["id"]) in (R, NR) else None}
            for r in rows if r["hygiene_changed"]]


def score_set(rows: list[dict[str, Any]], truth: dict[str, str], sheet_by_id: dict[str, dict] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for st in STRATA:
        rs = [r for r in rows if st == "ALL" or r["stratum"] == st]
        out[st] = {"cases": len(rs), "apps": len({r["app_repo"] for r in rs}),
                   "truth": dict(Counter(truth.get(r["id"], "MISSING") for r in rs)),
                   "unknown_truth": sum(1 for r in rs if truth.get(r["id"]) == UNKNOWN),
                   "tools": {t: tool_scores(rs, truth, t) for t in TOOLS},
                   "paired": {a: paired(rs, truth, a) for a in ("hygiene", "legacy")},
                   "hygiene_vs_legacy": paired(rs, truth, "hygiene", "legacy"),
                   "govulncheck_levels": dict(Counter((r.get("govulncheck") or {}).get("level") for r in rs)),
                   "hygiene_changes": hygiene_changes(rs, truth)}
        if sheet_by_id is not None:
            out[st]["path_precision"] = path_precision(rs, sheet_by_id)
    return out


def intervals_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool | None:
    if not a["n"] or not b["n"]:
        return None
    return not (a["ci_high"] < b["ci_low"] or b["ci_high"] < a["ci_low"])
