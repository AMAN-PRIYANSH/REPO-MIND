"""Lifting evaluation on D1 (CP5b deliverable 4): `python -m vulntrace eval lift`.

Per case (resumable, evidence kept in the gitignored `data/lift/`): unpack the vulnerable side of
the fix commit, prepare the module, and run the helper's `lift` mode once with every seed the
experiments need: the vulndb core symbols (the known root cause) and the symbols the committed
CP5 E1 runs selected. Scoring is separate, pure, and reads only those per-case files:

- lifting against the vulndb's own `derived_symbols` (precision/recall per case, macro-averaged,
  cluster bootstrap by D1 `cluster_key`), for the NEAREST and ALL stopping rules, with coverage
  next to every rate;
- E1+L: the committed E1 selections lifted, scored against core ∪ derived, paired with E1 and E0.

Symbols are compared by name (not package path), the project convention (`dataset/baselines.py`).
A case whose module cannot be prepared or loaded keeps its status and first error line and is
counted in the coverage table; it is never dropped.
"""

import json
import posixpath
import shutil
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np

from vulntrace.dataset import baselines, git_fetch, materialize
from vulntrace.eval import cp5_stats as st
from vulntrace.eval import lift_prep
from vulntrace.methods import lift as lift_method

SCHEMA_VERSION = "1.0"
RULES = ("NEAREST", "ALL")
OK_STATUSES = (lift_method.STATUS_LIFTED, lift_method.STATUS_ALREADY)
MAX_LIFT_DEPTH = lift_method.DEFAULT_MAX_LIFT_DEPTH
LIFT_TIMEOUT_S = 900.0

# per-case failure categories (a case that lifted nothing)
F_NO_SOURCE, F_NO_MODULE, F_PREP = "NO_SOURCE", "NO_MODULE", "PREP_FAILED"
F_LOAD, F_TIMEOUT, F_ROOT_ONLY, F_SEED_ERROR = "LOAD_FAILED", "TIMEOUT", "ROOT_ONLY", "SEED_ERROR"
F_NOT_RUN = "NOT_RUN"


def import_path_for(module_path: str, module_rel: str, package_dir: str) -> str | None:
    """Import path of a repository-relative package directory inside the module rooted at
    `module_rel` (both repo-relative, forward slashes); None if the directory is outside the module."""
    rel = posixpath.relpath(package_dir or ".", module_rel or ".")
    if rel == ".":
        return module_path
    if rel.startswith(".."):
        return None
    return module_path + "/" + rel


def core_seeds(module: dict[str, Any]) -> list[dict[str, str]]:
    return [{"package": p["package"], "symbol": s, "origin": "CORE"} for p in module["packages"] for s in p["core_symbols"]]


def selected_seeds(evidence: dict[str, Any], selected_ids: list[str], module_path: str, module_rel: str,
                   origin: str) -> list[dict[str, str]]:
    """The seeds an E1 selection contributes in this module (candidates outside it are skipped)."""
    by_id = {c["candidate_id"]: c for c in evidence["candidates"]}
    out = []
    for cid in selected_ids:
        c = by_id.get(cid)
        if c is None:
            continue
        pkg = import_path_for(module_path, module_rel, c["package_dir"])
        if pkg is not None:
            out.append({"package": pkg, "symbol": c["symbol"], "origin": origin})
    return out


def e1_selected_ids(e1_docs: dict[str, dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    """{case id: {alias: [candidate ids]}} for the VALID E1 rows of the committed CP5 files."""
    out: dict[str, dict[str, list[str]]] = {}
    for alias, doc in e1_docs.items():
        for r in doc["rows"]:
            if r["llm"]["status"] == "VALID":
                out.setdefault(r["id"], {})[alias] = list(r["llm"]["selected"])
    return out


def dedupe(seeds: list[dict[str, str]]) -> list[dict[str, str]]:
    seen, out = set(), []
    for s in seeds:
        k = (s["package"], s["symbol"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


# --- running ---------------------------------------------------------------------------------------
_REPO_LOCKS: dict[str, threading.Lock] = {}
_REPO_LOCKS_GUARD = threading.Lock()


def repo_lock(repo_dir: Path) -> threading.Lock:
    """One lock per cached clone: concurrent fetches into one repository fight over git's lock files."""
    with _REPO_LOCKS_GUARD:
        return _REPO_LOCKS.setdefault(str(repo_dir), threading.Lock())


def ensure_parent(fc: dict[str, str], repo_cache: Path | None, fetch=git_fetch.fetch_commit) -> tuple[Path, str | None, str | None]:
    """(repo dir, parent sha or None, error line or None). Fetches the commit (depth 2) again if a later
    fetch of another commit in the same clone cut its parent off (`.git/shallow`), so the result does
    not depend on which cases ran before."""
    repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], repo_cache)
    with repo_lock(repo_dir):
        try:
            fetch(fc["host"], fc["owner"], fc["repo"], fc["sha"], cache_root=repo_cache)
        except git_fetch.GitFetchError as exc:
            return repo_dir, None, f"{exc.code}: {git_fetch.first_error_line(exc.message)}"
        parent = git_fetch.parent_sha(repo_dir, fc["sha"])
    if parent is None:
        return repo_dir, None, f"commit {fc['sha'][:12]} has no parent in the fetched history"
    return repo_dir, parent, None


def run_case(case: dict[str, Any], evidence: dict[str, Any] | None, selections: dict[str, list[str]], *,
             repo_cache: Path | None, work_dir: Path, gomodcache: Path, binary: Path | None = None,
             timeout: float = LIFT_TIMEOUT_S, keep_tree: bool = False, runner=None,
             prepare: Callable[..., dict[str, Any]] = lift_prep.prepare_case) -> dict[str, Any]:
    """Run the lift for one D1 case and return its full per-case artifact (written by the caller)."""
    started = time.monotonic()
    art: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "case_id": case["id"], "modules": [], "seeds_by_origin": {}}
    fc = case["fix_commits"][0] if case["fix_commits"] else None
    repo_dir, parent, fetch_err = ensure_parent(fc, repo_cache) if fc else (None, None, None)
    modules = [m for m in case["modules"] if any(p["core_symbols"] for p in m["packages"])]
    if fc is None or parent is None:
        reason = "no fix commit" if fc is None else f"fix commit or its parent unavailable: {fetch_err}"
        for m in modules:
            art["modules"].append({"module": m["module"], "prep": {"status": lift_prep.NO_SOURCE, "reason": reason,
                                                                   "module_rel": None}, "seeds": [], "records": []})
        art["seconds"] = round(time.monotonic() - started, 1)
        return art
    for m in modules:
        entry: dict[str, Any] = {"module": m["module"], "seeds": [], "records": []}
        prep = prepare(repo_dir, parent, m["module"], work_dir, gomodcache,
                       repo_prefix=f"{fc['host']}/{fc['owner']}/{fc['repo']}")
        entry["prep"] = {k: prep.get(k) for k in ("status", "reason", "module_rel", "synthesized_go_mod", "vendored")}
        if prep["status"] == lift_prep.READY:
            seeds = core_seeds(m)
            for alias, ids in sorted(selections.items()):
                seeds += selected_seeds(evidence or {"candidates": []}, ids, m["module"], prep["module_rel"] or "", f"E1:{alias}")
            seeds = dedupe(seeds)
            entry["seeds"] = seeds
            t0 = time.monotonic()
            entry["records"] = lift_method.run_lift(Path(prep["module_dir"]), [{"package": s["package"], "symbol": s["symbol"]} for s in seeds],
                                                    limits={"max_lift_depth": MAX_LIFT_DEPTH}, timeout=timeout, binary=binary,
                                                    runner=runner)
            entry["lift_seconds"] = round(time.monotonic() - t0, 1)
        art["modules"].append(entry)
    if not keep_tree:
        shutil.rmtree(work_dir / "tree", ignore_errors=True)
    art["seconds"] = round(time.monotonic() - started, 1)
    return art


# --- per-case reading ---------------------------------------------------------------------------------
def _names(entries: list[dict[str, Any]]) -> set[str]:
    return {e["symbol"] for e in entries}


def seed_lifts(art: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """{(package, symbol): lift record} over all modules of the case."""
    out = {}
    for m in art["modules"]:
        for rec in m["records"]:
            out[(rec["target"]["package"], rec["target"]["symbol"])] = rec
    return out


def case_outcome(art: dict[str, Any]) -> dict[str, Any]:
    """Did lifting work on this case, from the core seeds? Returns {success, failure, detail,
    module_loaded, seed_status}."""
    status: dict[str, str] = {}
    failure, detail, loaded = None, None, False
    for m in art["modules"]:
        prep = m["prep"]
        if prep["status"] != lift_prep.READY:
            failure = failure or {lift_prep.NO_SOURCE: F_NO_SOURCE, lift_prep.NO_MODULE: F_NO_MODULE,
                                  lift_prep.PREP_FAILED: F_PREP}[prep["status"]]
            detail = detail or prep["reason"]
            continue
        for rec in m["records"]:
            if rec["error"] and rec["error"]["code"] in ("LOAD_FAILED", "TIMEOUT", "HELPER_MISSING", "BAD_RESPONSE", "CONTRACT_MISMATCH"):
                failure = failure or (F_TIMEOUT if rec["error"]["code"] == "TIMEOUT" else F_LOAD)
                detail = detail or f"{rec['error']['code']}: {rec['error']['message']}"
            else:
                loaded = True
            if rec["target"]["symbol"] and any(s["origin"] == "CORE" and (s["package"], s["symbol"]) == (rec["target"]["package"], rec["target"]["symbol"])
                                               for s in m["seeds"]):
                status[f"{rec['target']['package']}::{rec['target']['symbol']}"] = rec["status"] if not rec["error"] else rec["error"]["code"]
    success = any(v in OK_STATUSES for v in status.values())
    if not success and failure is None:
        codes = set(status.values())
        failure = F_ROOT_ONLY if codes <= {lift_method.STATUS_ROOT_ONLY, lift_method.STATUS_NOT_IN_PROGRAM} and codes else F_SEED_ERROR
        detail = detail or ", ".join(f"{k.split('::')[1]}={v}" for k, v in sorted(status.items()))[:300]
    if not art["modules"]:
        failure, detail = F_NO_MODULE, "no module with core symbols"
    return {"success": success, "failure": None if success else failure, "detail": None if success else detail,
            "module_loaded": loaded, "seed_status": status}


def lifted_set(art: dict[str, Any], rule: str, origin_prefix: str = "CORE", exclude: set[str] | None = None) -> set[str]:
    """Names lifted from the seeds of one origin (CORE, or an E1 alias), under one stopping rule."""
    out: set[str] = set()
    for m in art["modules"]:
        origins = {(s["package"], s["symbol"]): s["origin"] for s in m["seeds"]}
        for rec in m["records"]:
            if rec["status"] in OK_STATUSES and origins.get((rec["target"]["package"], rec["target"]["symbol"]), "").startswith(origin_prefix):
                out |= _names(rec["rules"].get(rule, {}).get("entries", []))
    return out - (exclude or set())


# --- scoring: lifting vs derived_symbols ----------------------------------------------------------------
def derived_names(case: dict[str, Any]) -> set[str]:
    return baselines.core_and_derived_symbols(case) - baselines.core_symbols(case)


def score_cases(cases_by_id: dict[str, dict], d1_entries: list[dict[str, Any]], arts: dict[str, dict]) -> list[dict[str, Any]]:
    """One compact row per D1 case that has derived_symbols (the population of the lifting evaluation)."""
    rows = []
    for e in sorted(d1_entries, key=lambda x: x["id"]):
        case = cases_by_id[e["id"]]
        derived = derived_names(case)
        if not derived:
            continue
        art = arts.get(e["id"])
        core = baselines.core_symbols(case)
        row = {"id": e["id"], "cluster_key": materialize.d1_cluster_key(case), "created": case["created"],
               "evidence_status": e["status"], "n_core": len(core), "n_derived": len(derived), "derived": sorted(derived),
               "core": sorted(core)}
        if art is None:
            row.update(outcome={"success": False, "failure": F_NOT_RUN, "detail": "no per-case result", "module_loaded": False,
                                "seed_status": {}}, lifted={r: [] for r in RULES}, synthesized_go_mod=False)
        else:
            out = case_outcome(art)
            row["outcome"] = out
            row["synthesized_go_mod"] = any(m["prep"].get("synthesized_go_mod") for m in art["modules"])
            row["lifted"] = {r: sorted(lifted_set(art, r)) for r in RULES} if out["success"] else {r: [] for r in RULES}
            row["seconds"] = art.get("seconds")
        row["metrics"] = {}
        for r in RULES:
            lit = set(row["lifted"][r])
            new = lit - set(core)
            row["metrics"][r] = {"literal": st.set_metrics(lit, derived), "new_only": st.set_metrics(new, derived)}
        rows.append(row)
    return rows


def _group(rows: list[dict[str, Any]]) -> st.Group:
    return st.Group([r["cluster_key"] for r in rows])


def _summ(rows: list[dict[str, Any]], pick: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Macro averages with cluster-bootstrap intervals over `rows` (precision only over rows that
    predicted something, with that count)."""
    if not rows:
        return {"n": 0}
    ms = [pick(r) for r in rows]
    g = _group(rows)
    mat = st.matrix(ms)
    s = dict(zip(st.COLUMNS, g.summary(mat)))
    with_pred = [i for i, m in enumerate(ms) if m["precision"] is not None]
    prec = None
    if with_pred:
        sub = [rows[i] for i in with_pred]
        gp = _group(sub)
        prec = gp.summary(np.array([[ms[i]["precision"]] for i in with_pred], dtype=np.float64))[0]
        prec["n_with_prediction"] = len(with_pred)
    return {"n": len(rows), "n_clusters": g.n_clusters, "precision": prec, "recall": s["recall"], "f1": s["f1"],
            "any_hit": s["any_hit"], "exact": s["exact"], "abstain": s["abstain"]}


def summarize_lifting(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts, failure reasons, and per-rule metrics with coverage next to every rate."""
    n = len(rows)
    ok = [r for r in rows if r["outcome"]["success"]]
    fails = Counter(r["outcome"]["failure"] for r in rows if not r["outcome"]["success"])
    detail = {}
    for r in rows:
        if not r["outcome"]["success"]:
            detail.setdefault(r["outcome"]["failure"], []).append({"id": r["id"], "detail": r["outcome"]["detail"]})
    out: dict[str, Any] = {
        "cases_with_derived": n, "module_loaded": sum(1 for r in rows if r["outcome"]["module_loaded"]),
        "lifted_ok": len(ok), "coverage": {"lifted_ok": len(ok), "of": n, "rate": len(ok) / n if n else float("nan")},
        "failure_counts": dict(sorted(fails.items())), "failure_detail": detail,
        "lifted_with_synthesized_go_mod": sum(1 for r in ok if r.get("synthesized_go_mod")),
        "clusters": len({r["cluster_key"] for r in rows}), "rules": {},
    }
    for rule in RULES:
        entry: dict[str, Any] = {}
        for view in ("literal", "new_only"):
            pick = lambda r, rule=rule, view=view: r["metrics"][rule][view]
            entry[view] = {"on_lifted": _summ(ok, pick), "all_attempted": _summ(rows, pick)}
        entry["lifted_set_size"] = {"mean": float(np.mean([len(r["lifted"][rule]) for r in ok])) if ok else float("nan"),
                                    "max": max((len(r["lifted"][rule]) for r in ok), default=0)}
        out["rules"][rule] = entry
    if ok:
        g = _group(ok)
        a = st.matrix([r["metrics"]["ALL"]["literal"] for r in ok])
        b = st.matrix([r["metrics"]["NEAREST"]["literal"] for r in ok])
        out["all_minus_nearest"] = {"n": len(ok), **{c: d for c, d in zip(st.COLUMNS, g.paired(a, b))
                                                       if c in ("precision0", "recall", "f1", "any_hit")}}
    return out


def worked_examples(rows: list[dict[str, Any]], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    """Cases where lifting matches the curator's derived symbols exactly, and cases where it does not
    (so a low score can be read as convention or as a miss). Chosen by id order, not by outcome."""
    ok = [r for r in rows if r["outcome"]["success"]]
    pick = lambda r: {"id": r["id"], "core": r["core"], "derived": r["derived"], "NEAREST": r["lifted"]["NEAREST"], "ALL": r["lifted"]["ALL"]}
    exact = [pick(r) for r in ok if set(r["lifted"]["ALL"]) - set(r["core"]) == set(r["derived"])][:limit]
    diff = [pick(r) for r in ok if set(r["lifted"]["ALL"]) - set(r["core"]) != set(r["derived"])][:limit]
    return {"exact": exact, "different": diff}


# --- E1 + L ---------------------------------------------------------------------------------------------
VARIANTS = (("replace", "NEAREST"), ("replace", "ALL"), ("add", "NEAREST"), ("add", "ALL"))


def e1_plus_l_sets(art: dict[str, Any] | None, alias: str, selected_syms: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """For one case and model: {variant key: predicted names}. `selected_syms` are the (package, symbol)
    of the E1 selection. `replace`: a selected symbol that lifted is replaced by its entry points, one
    that did not (ROOT_ONLY, load failure) stays (origin ROOT_ONLY). `add`: selection plus lifted entries."""
    recs = seed_lifts(art) if art else {}
    out = {}
    for variant, rule in VARIANTS:
        pred: set[str] = set()
        for pkg, sym in selected_syms:
            rec = recs.get((pkg, sym))
            lifted = _names(rec["rules"].get(rule, {}).get("entries", [])) if rec and rec["status"] in OK_STATUSES else set()
            if variant == "replace":
                pred |= lifted if lifted else {sym}
            else:
                pred |= lifted | {sym}
        out[f"{variant}/{rule}"] = pred
    return out


def e1_plus_l_rows(case_list_ids: list[str], cases_by_id: dict[str, dict], evidence_by_id: dict[str, dict],
                   e1_doc: dict[str, Any], arts: dict[str, dict]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Per-case E1+L rows for one model, plus counts of what was and was not mappable."""
    alias = e1_doc["model"]["alias"]
    rows, skipped = [], Counter()
    for r in e1_doc["rows"]:
        cid = r["id"]
        ev = evidence_by_id.get(cid)
        if ev is None or ev["status"] != "AVAILABLE":
            skipped["no_evidence"] += 1
            continue
        if len(ev["candidates"]) != r["n_candidates"]:
            skipped["evidence_changed_since_cp5"] += 1   # candidate ids no longer map to the same functions
            continue
        case = cases_by_id[cid]
        core, derived = baselines.core_symbols(case), baselines.core_and_derived_symbols(case)
        by_id = {c["candidate_id"]: c for c in ev["candidates"]}
        selected = r["llm"]["selected"] if r["llm"]["status"] == "VALID" else []
        names = [by_id[i]["symbol"] for i in selected if i in by_id]
        art = arts.get(cid)
        # (package, symbol) per selected candidate in the module that was analysed
        pk: list[tuple[str, str]] = []
        if art:
            for m in art["modules"]:
                if m["prep"]["status"] == lift_prep.READY:
                    for s in m["seeds"]:
                        if s["origin"] == f"E1:{alias}":
                            pk.append((s["package"], s["symbol"]))
        pk = sorted(set(pk))
        sets = e1_plus_l_sets(art, alias, pk) if pk else {f"{v}/{rule}": set(names) for v, rule in VARIANTS}
        # symbols selected outside the analysed module stay as they are
        extra = set(names) - {s for _p, s in pk}
        sets = {k: v | extra for k, v in sets.items()}
        applied = bool(art) and any(m["prep"]["status"] == lift_prep.READY and any(
            rec["status"] in OK_STATUSES for rec in m["records"]) for m in art["modules"]) and bool(pk)
        changed = any(sets[k] != set(names) for k in sets)
        e0_names = baselines.e0_predict(ev)
        row = {"id": cid, "cluster_key": r["cluster_key"], "created": r["created"], "lifting_applied": applied, "changed": changed,
               "n_selected": len(names), "gold": {"core": sorted(core), "core_derived": sorted(derived)},
               "sets": {"e0": sorted(e0_names), "e1": sorted(names), **{k: sorted(v) for k, v in sets.items()}}}
        mm = row_metrics(row)
        # the recomputed E0 and E1 must equal the committed ones, else the mapping is wrong for this case
        committed, committed_e0 = r["m"]["llm"]["core_derived"], r["m"]["e0"]["core_derived"]
        if (abs(mm["core_derived"]["e1"]["recall"] - committed["recall"]) > 1e-9 or mm["core_derived"]["e1"]["predicted"] != committed["predicted"]
                or abs(mm["core_derived"]["e0"]["recall"] - committed_e0["recall"]) > 1e-9):
            skipped["e1_not_reproduced"] += 1
            continue
        rows.append(row)
    return rows, dict(skipped)


def row_metrics(row: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """{gold: {method: set metrics}} recomputed from a row's stored sets and gold lists."""
    return {g: {m: st.set_metrics(sset, row["gold"][g]) for m, sset in row["sets"].items()} for g in ("core", "core_derived")}


def summarize_e1_plus_l(rows: list[dict[str, Any]], cutoff: str | None, group_defs: Callable) -> dict[str, Any]:
    """Per group (headline / all ...) and per gold: summaries for E0, E1 and each E1+L variant, plus paired
    differences of each E1+L variant to E1 and to E0. `group_defs(rows, cutoff)` is llm_report's."""
    out: dict[str, Any] = {}
    methods = ["e0", "e1"] + [f"{v}/{rule}" for v, rule in VARIANTS]
    for key, label, mask in group_defs(rows, cutoff):
        sub = [r for r, m in zip(rows, mask) if m]
        if not sub:
            out[key] = {"label": label, "n": 0}
            continue
        g = _group(sub)
        metrics = {r["id"]: row_metrics(r) for r in rows}
        g_applied = [r for r in sub if r["lifting_applied"]]
        entry: dict[str, Any] = {"label": label, "n": len(sub), "n_clusters": g.n_clusters,
                                 "lifting_applied": len(g_applied), "selection_changed": sum(1 for r in sub if r["changed"])}
        for gold in ("core", "core_derived"):
            mats = {m: st.matrix([metrics[r["id"]][gold][m] for r in sub]) for m in methods}
            entry[gold] = {"summary": {m: dict(zip(st.COLUMNS, g.summary(mats[m]))) for m in methods}, "paired_vs_e1": {}, "paired_vs_e0": {}}
            for m in methods[2:]:
                for base, slot in (("e1", "paired_vs_e1"), ("e0", "paired_vs_e0")):
                    entry[gold][slot][m] = dict(zip(st.COLUMNS, g.paired(mats[m], mats[base])))
            if g_applied:
                ga = _group(g_applied)
                am = {m: st.matrix([metrics[r["id"]][gold][m] for r in g_applied]) for m in methods}
                entry[gold]["applied_only"] = {
                    "n": len(g_applied), "n_clusters": ga.n_clusters,
                    "paired_vs_e1": {m: dict(zip(st.COLUMNS, ga.paired(am[m], am["e1"]))) for m in methods[2:]}}
        out[key] = entry
    return out


# --- the results document --------------------------------------------------------------------------------
def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
