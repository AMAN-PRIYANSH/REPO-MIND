"""`python -m vulntrace eval triage --set d3` (CP7b deliverable 2, and the optional reference of
deliverable 3).

For every case of `docs/results/cp7b/d3_cases.json`: build the advisory's evidence (fix diff; a
release range only if the fix evidence is unusable), take the application tree that `d3 select`
extracted (or extract it again the same way), and run the CP7 pipeline unchanged
(`triage.run_triage`, mode `auto`, verifier on, Mode 2 policy `DOWNGRADE`). The app is a
separate module: the vulnerable code is a dependency in the module cache. govulncheck, where it
runs, is recorded next to each verdict and labelled as a reference, not truth.

Committed: one compact row per case and a summary (`d3_triage.json`), and every full verdict with
local paths rewritten (`verdicts/<case>.json`; module-cache files become `$GOMODCACHE/...`). Each
file is under 512 KiB. Not committed: trees, module caches, evidence (`data/d3/`).
"""

import gzip
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from vulntrace.d3 import govuln
from vulntrace.d3 import select as sl
from vulntrace.dataset import datasets, fix_evidence, git_fetch
from vulntrace.dataset import materialize as mat
from vulntrace.eval import triage_eval as te
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import triage
from vulntrace.verdict import CANT_DETERMINE, NOT_REACHABLE, REACHABLE

SCHEMA_VERSION = "1.0"
MAX_MAINS = 10      # the triage default; selection rule A9 keeps apps with at most this many


# --- evidence --------------------------------------------------------------------------------------
def advisory_for(vcase: dict[str, Any], module: str) -> dict[str, Any]:
    """The VulnCase with `module`, `vulnerable_at` and `fixed_in` of the module the app requires."""
    adv = dict(vcase)
    entry = next((m for m in vcase["modules"] if m["module"] == module), None)
    if entry:
        adv.update(module=module, vulnerable_at=entry["vulnerable_at"], fixed_in=entry["fixed_in"])
    else:
        adv["module"] = module
    return adv


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def ensure_evidence(case: dict[str, Any], vcase: dict[str, Any], evidence_dir: Path, binary,
                    build_fix: Callable | None = None, build_range: Callable | None = None) -> dict[str, Any]:
    """{fix_evidence, release_range, candidate_code} for one advisory, built once and stored under
    `evidence_dir` (layout of `data/`, so `inputs.load_evidence` reads it). A release range is built
    only when the fix evidence is not usable (Mode 2 is then the pipeline's own choice)."""
    aid = case["advisory"]
    build_fix = build_fix or (lambda vc: fix_evidence.build_fix_evidence(vc["id"], vc["fix_commits"], binary=binary))
    fe_path = evidence_dir / "fix_evidence" / f"{aid}.json"
    fe = _read(fe_path)
    if fe is None or fe.get("case_id") != aid:
        fe = build_fix(vcase)
        _write(fe_path, fe)
    rr = cc = None
    if not (fe.get("status") == "AVAILABLE" and fe.get("candidates")):
        rr_path, cc_path = evidence_dir / "release_range" / f"{aid}.json", evidence_dir / "candidate_code" / f"{aid}.json"
        rr, cc = _read(rr_path), _read(cc_path)
        if rr is None or cc is None:
            module = next((m for m in vcase["modules"] if m["module"] == case["module"] and m["vulnerable_at"]
                           and m["fixed_in"]), None)
            if module is not None:
                build_range = build_range or (lambda vc, m: datasets.d4_candidate_count(vc, m, binary, None))
                rr = build_range(vcase, module)
                fc = vcase["fix_commits"][0]
                repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"])
                cc = (mat.extract_candidate_code(repo_dir, rr) if rr.get("candidates") else
                      {"case_id": aid, "candidates": {}, "missing_bodies": 0, "complete": True})
                _write(rr_path, rr)
                _write(cc_path, cc)
    return {"fix_evidence": fe, "release_range": rr, "candidate_code": cc}


# --- paths in committed files ----------------------------------------------------------------------
def sanitise(obj: Any, gomodcache: Path, goroot: str | None = None) -> Any:
    """Committed copy: module-cache paths become `$GOMODCACHE/...`, a GOROOT path `$GOROOT/...`,
    any other local absolute path `<local>` (te.example_verdict)."""
    text = json.dumps(obj)
    for root, label in ((str(gomodcache.resolve()), "$GOMODCACHE"), (str(gomodcache), "$GOMODCACHE"),
                        (goroot or "", "$GOROOT")):
        if root:
            text = te.replace_root(text, root, label)
    return te.example_verdict(json.loads(text))


# --- one case --------------------------------------------------------------------------------------
def run_case(case: dict[str, Any], vcase: dict[str, Any] | None, *, evidence_dir: Path, app_dir: Path | None,
             app_error: str | None, runners: triage.Runners, binary, gv: dict[str, Any] | None,
             vulndb_commit: str, repo_commit: str | None,
             build_fix: Callable | None = None, build_range: Callable | None = None) -> tuple[dict, dict | None]:
    """(compact row, full verdict or None)."""
    t0 = time.monotonic()
    row: dict[str, Any] = {k: case[k] for k in ("id", "advisory", "app_repo", "app_tag", "app_commit", "module",
                                                "version_selected", "created")}
    row["cluster_key"] = case["app_repo"]          # cases of one application are not independent
    if vcase is None:
        row.update(harness_error="advisory not in the pinned vulndb snapshot", verdict=None)
        return row, None
    ev = ensure_evidence(case, vcase, evidence_dir, binary, build_fix, build_range)
    row["fix_evidence_status"] = (ev["fix_evidence"] or {}).get("status")
    row["fix_candidates"] = len((ev["fix_evidence"] or {}).get("candidates") or [])
    row["release_range_status"] = (ev["release_range"] or {}).get("status")
    if app_dir is None:
        row.update(app_prep_error=app_error, verdict=None, mode=None, pre_policy_verdict=None, reason_codes=[])
        row["case_seconds"] = round(time.monotonic() - t0, 1)
        return row, None
    req = triage.TriageRequest(case_id=case["id"], app=app_dir, mode="auto", advisory=advisory_for(vcase, case["module"]),
                               fix_evidence=ev["fix_evidence"], release_range=ev["release_range"],
                               candidate_code=ev["candidate_code"], max_mains=MAX_MAINS, commit=case["app_commit"],
                               vulndb_commit=vulndb_commit, repo_commit=repo_commit)
    v = triage.run_triage(req, runners)
    row.update(te.verdict_row(v))
    row["schema_errors"] = te._check_schema(v)[:3]
    row["reachable_symbols"] = sorted({f"{e['target']['package']}.{e['target']['symbol']}" for e in v["per_symbol"]
                                       if e["result"] == REACHABLE})
    row["helper_go_version"] = ((v.get("toolchain") or {}).get("helper") or {}).get("go_version")
    row["linker_go_version"] = ((v.get("toolchain") or {}).get("linker") or {}).get("go_version")
    if gv is not None:
        g = govuln.advisory_result(gv, case["advisory"])
        row["govulncheck"] = {**g, "agreement": govuln.agreement(v["verdict"], g["verdict"])}
    row["case_seconds"] = round(time.monotonic() - t0, 1)
    return row, v


# --- summary ---------------------------------------------------------------------------------------
def cd_reason(row: dict[str, Any]) -> str:
    """The CANT_DETERMINE reason of a row: its reason codes, joined (stable order)."""
    return "+".join(sorted(row.get("reason_codes") or [])) or "NONE"


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ran = [r for r in rows if r.get("verdict")]
    verdicts = Counter(r["verdict"] for r in ran)
    pre_policy = Counter(r.get("pre_policy_verdict") for r in ran)
    modes = Counter(r.get("mode") for r in ran)
    cd = [r for r in ran if r["verdict"] == CANT_DETERMINE]
    failures = [{"id": r["id"], "reason": r.get("harness_error") or r.get("app_prep_error")}
                for r in rows if not r.get("verdict")]
    gvs = [r["govulncheck"] for r in rows if r.get("govulncheck")]
    apps: dict[str, dict[str, int]] = {}
    for r in ran:
        apps.setdefault(r["app_repo"], Counter())[r["verdict"]] += 1
    return {
        "cases": len(rows), "triaged": len(ran), "not_triaged": failures,
        "verdicts": {k: verdicts.get(k, 0) for k in (REACHABLE, NOT_REACHABLE, CANT_DETERMINE)},
        "pre_policy_verdicts": dict(pre_policy), "modes": dict(modes),
        "cant_determine_reasons": dict(Counter(cd_reason(r) for r in cd)),
        "verification": dict(Counter((r.get("verification") or {}).get("status") for r in ran)),
        "verifier_downgrades": sum((r.get("verification") or {}).get("downgraded") or 0 for r in ran),
        "per_app": {a: dict(c) for a, c in sorted(apps.items())},
        "seconds_per_case": te.seconds_summary([r.get("case_seconds") for r in rows]),
        "triage_seconds": te.seconds_summary([r.get("seconds") for r in ran]),
        "toolchain": {"helper": sorted({r.get("helper_go_version") for r in ran if r.get("helper_go_version")}),
                      "linker": sorted({r.get("linker_go_version") for r in ran if r.get("linker_go_version")})},
        "govulncheck": {"runs": len(gvs), "verdicts": dict(Counter(g["verdict"] for g in gvs)),
                        "agreement": dict(Counter(g["agreement"] for g in gvs)),
                        "disagreements": [{"id": r["id"], "ours": r["verdict"], "govulncheck": r["govulncheck"]["verdict"],
                                           "level": r["govulncheck"]["level"]}
                                          for r in rows if (r.get("govulncheck") or {}).get("agreement") == "DISAGREE"],
                        "not_affected": [r["id"] for r in rows
                                         if (r.get("govulncheck") or {}).get("verdict") == govuln.NOT_AFFECTED]},
    }


# --- the run ---------------------------------------------------------------------------------------
def eval_d3(case_doc: dict[str, Any], *, cases_by_id: dict[str, dict], data_dir: Path, gomodcache: Path,
            cache_root: Path, base: triage.Runners, binary, vulndb_commit: str, repo_commit: str | None,
            gv_exe: Path | None, gv_db: Path | None, only: list[str] | None = None, rerun: bool = False,
            log=print) -> tuple[dict[str, Any], dict[str, dict]]:
    """(results document, {case id: full verdict}). Cases of one application share memoised
    methods (one call graph and one build per main package and target)."""
    cases = case_doc["cases"]
    if only:
        cases = [c for c in cases if c["id"] in set(only)]
    out_dir = data_dir / "triage"
    evidence_dir = data_dir / "evidence"
    work_root = data_dir / "apps"
    probe = sl.Probe(cache_root=cache_root, work_root=work_root, gomodcache=gomodcache, log=log)
    rows, verdicts = [], {}
    by_app: dict[str, list[dict[str, Any]]] = {}
    for c in cases:
        by_app.setdefault(c["app_repo"], []).append(c)
    for repo, app_cases in by_app.items():
        commit = app_cases[0]["app_commit"]
        todo = [c for c in app_cases if rerun or not (out_dir / f"{c['id']}.row.json").is_file()]
        app_dir, app_err, gv = None, None, None
        if todo:
            t0 = time.monotonic()
            app_dir = sl.app_tree_dir(work_root, repo, commit)
            if not (app_dir / "go.mod").is_file():
                app_dir, app_err = probe.prepare(repo, commit)
                if app_err:
                    app_dir = None
            log(f"{repo}@{app_cases[0]['app_tag']}: tree {'ready' if app_dir else 'FAILED: ' + str(app_err)} "
                f"({time.monotonic() - t0:.0f}s)")
            if app_dir is not None and gv_exe is not None and gv_db is not None:
                t1 = time.monotonic()
                gv = govuln.run_govulncheck(gv_exe, gv_db, app_dir, app_cases[0]["mains"], gomodcache)
                gv["seconds"] = round(time.monotonic() - t1, 1)
                log(f"  govulncheck: ok={gv['ok']} {gv.get('error') or ''} ({gv['seconds']}s)")
        runners = te.memo_runners(base)
        for c in app_cases:
            row_path = out_dir / f"{c['id']}.row.json"
            if c in todo:
                row, v = run_case(c, cases_by_id.get(c["advisory"]), evidence_dir=evidence_dir, app_dir=app_dir,
                                  app_error=app_err, runners=runners, binary=binary, gv=gv, vulndb_commit=vulndb_commit,
                                  repo_commit=repo_commit)
                if gv is not None:
                    row.setdefault("govulncheck", {})["run"] = {k: gv.get(k) for k in ("scanner", "go_version", "exit_code",
                                                                                      "seconds", "error")}
                _write(row_path, row)
                if v is not None:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    with gzip.open(out_dir / f"{c['id']}.verdict.json.gz", "wt", encoding="utf-8") as f:
                        json.dump(v, f, sort_keys=True)
                log(f"  {c['id']}: mode={row.get('mode')} verdict={row.get('verdict')} reasons={row.get('reason_codes')} "
                    f"govulncheck={(row.get('govulncheck') or {}).get('verdict')} {row.get('case_seconds')}s")
            row = _read(row_path)
            rows.append(row)
            vp = out_dir / f"{c['id']}.verdict.json.gz"
            if vp.is_file():
                with gzip.open(vp, "rt", encoding="utf-8") as f:
                    verdicts[c["id"]] = json.load(f)
    doc = {"schema_version": SCHEMA_VERSION, "set": "d3", "rows": rows, "summary": summarise(rows),
           "max_mains": MAX_MAINS, "mode2_policy": "DOWNGRADE",
           "env": {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOPROXY": "off (analysis)", "GOFLAGS": "-mod=readonly"},
           "statement": "REACHABLE means reachable in the call graph from a main package, not exploitable. "
                        "govulncheck is a reference, not truth; truth comes from the adjudication sheets."}
    return doc, verdicts


def goroot() -> str | None:
    import subprocess

    from vulntrace.env import go_env

    try:
        p = subprocess.run(["go", "env", "GOROOT"], capture_output=True, text=True, env=go_env(), timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() or None


def results_root() -> Path:
    return REPO_ROOT / "docs" / "results" / "cp7b"


def setup_env(gomodcache: Path) -> None:
    """Shared by the helper, `go build`, `go list` (as in `eval triage --set d1/d4`)."""
    gomodcache.mkdir(parents=True, exist_ok=True)
    os.environ["GOMODCACHE"] = str(gomodcache)
    os.environ["GOCACHE"] = str(gomodcache.parent / (gomodcache.name + "-gocache"))
    os.environ["GOWORK"] = "off"
