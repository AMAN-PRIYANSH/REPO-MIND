"""Renders docs/results/CP7_TRIAGE_RESULTS.md from the files `eval triage` writes to
docs/results/cp7/ (fixtures.json, d1.json, d4.json). Every number comes from those files.

The headline sentence below was fixed in code before any CP7 result was produced, and is not
edited after (CP6 review note 5)."""

import json
from pathlib import Path
from typing import Any

from vulntrace.eval.triage_eval import POLICY_RULE_TEXT, VERDICTS, decide_mode2_policy

HEADLINE = ("CP7 runs the whole triage pipeline (two reachability methods, the rule table, the evidence verifier "
            "and the Mode 2 policy) on the 22 synthetic fixtures in three modes, where the truth is known, and on "
            "D1/D4 real modules analysed as their own application, where it is not: the fixture tables measure "
            "accuracy, the D1/D4 tables only measure verdict distributions, coverage and why the system abstains.")

MODE_LABEL = {"TARGETS": "TARGETS (the case's own target symbol)", "FIX": "FIX (Mode 1, synthetic fix commit)",
              "RELEASE": "RELEASE (Mode 2, synthetic release range)"}


def _load(d: Path, name: str) -> dict[str, Any] | None:
    p = d / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def pct(w: dict[str, Any]) -> str:
    if not w or not w.get("n"):
        return "n/a (0 cases)"
    return f"{w['rate']:.3f} [{w['ci_low']:.3f}, {w['ci_high']:.3f}] ({w['k']}/{w['n']})"


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def _counts(d: dict[str, int] | None) -> str:
    if not d:
        return "-"
    return ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: (-kv[1], str(kv[0]))))


def _env(doc: dict[str, Any]) -> list[str]:
    e = doc.get("environment") or {}
    return [f"- Command: `{e.get('command')}`", f"- Repository commit: `{e.get('repo_commit')}` (dirty: {e.get('repo_dirty')})",
            f"- OS: {e.get('os')}; Python {e.get('python')}; Go: {e.get('go')}"]


def render_fixtures(fx: dict[str, Any]) -> list[str]:
    out = ["## 1. Fixtures (D2, truth by construction)", ""] + _env(fx) + [""]
    out += ["Each of the 22 fixture cases is one main package and one target symbol whose truth is set by "
            "construction (CP1/CP2). TARGETS analyses that symbol directly. FIX and RELEASE use synthetic advisories "
            "built by `eval/triage_fixtures.py`: a throw-away git repository whose `v1.0.0` is the committed fixture "
            "module, a decoy commit that changes `vulnlib.Safe` and a fix commit that changes the target. The analysed "
            "app is the committed fixture module itself, restricted to the case's main package.", ""]
    out += ["Evidence the CP3 builders produced for each synthetic advisory:", ""]
    out += _table(["target", "advisory", "FIX candidates", "RELEASE candidates", "range commits"],
                  [[s, p["id"], ", ".join(p["fix_candidates"]), ", ".join(p["range_candidates"]), p["range_commits"]]
                   for s, p in sorted(fx["pack"].items())])
    out += ["", "FIX candidates beyond the target are functions within git's 3 context lines of the edit (CP3 attributes "
            "a hunk by its whole span); Mode 1 keeps them, as E0 did, and flags them `context_only`.", ""]
    out += ["### Summary per mode (false NOT_REACHABLE first)", ""]
    rows = []
    for mode, s in fx["summary"].items():
        f, p = s["final"], s["pre_policy"]
        rows.append([MODE_LABEL.get(mode, mode), f["false_not_reachable"], p["false_not_reachable"], f["false_reachable"],
                     f["cant_determine"], pct(f["accuracy"]), pct(f["coverage"]), pct(f["selective_accuracy"]),
                     pct(f["reachable_precision"]), s["verifier_rejections_on_correct"], s["verifier_downgrades"],
                     s["verified_paths"], s["reachable_without_verified_path"]])
    out += _table(["mode", "false NOT_REACHABLE (final)", "false NOT_REACHABLE (before policy)", "false REACHABLE",
                   "CANT_DETERMINE", "accuracy", "coverage (answered)", "selective accuracy", "REACHABLE precision",
                   "verifier rejections on correct outputs", "verifier downgrades (all)", "verified paths",
                   "REACHABLE without verified path"], rows)
    out += ["", "Rates are point estimates with 95% Wilson intervals and raw counts. Accuracy counts CANT_DETERMINE as "
            "not correct. RELEASE \"final\" is after the Mode 2 policy; \"before policy\" is the raw rule-table verdict.", ""]
    out += ["### Confusion matrices (truth rows, verdict columns)", ""]
    for mode, s in fx["summary"].items():
        for label, key in (("final", "final"), ("before policy", "pre_policy")):
            if mode != "RELEASE" and key == "pre_policy":
                continue
            m = s[key]["matrix"]
            out += [f"{MODE_LABEL.get(mode, mode)} - {label}:", ""]
            out += _table(["truth \\ verdict", *VERDICTS], [[t, *[m[t][v] for v in VERDICTS]] for t in m])
            out += [""]
    out += ["### Per case", ""]
    by: dict[str, dict[str, dict]] = {}
    for r in fx["rows"]:
        by.setdefault(r["id"], {})[r["mode"]] = r
    trows = []
    for cid, modes in by.items():
        t = modes.get("TARGETS", {})
        f = modes.get("FIX", {})
        rl = modes.get("RELEASE", {})

        def cell(r):
            if not r:
                return "-"
            codes = ",".join(r["reason_codes"]) if r["reason_codes"] else ""
            return r["verdict"] + (f" ({codes})" if codes else "")

        def analysed(r):
            return "; ".join(f"{a['symbol']}={a['result']}" for a in r.get("analysed", [])) or "-"

        trows.append([cid, t.get("truth"), cell(t), cell(f), analysed(f), cell(rl),
                      rl.get("pre_policy_verdict", "-"), analysed(rl)])
    out += _table(["case", "truth", "TARGETS", "FIX", "FIX symbols", "RELEASE (final)", "RELEASE before policy",
                   "RELEASE symbols"], trows)
    st = fx["stability"]
    out += ["", f"Determinism: the {st['cases']} TARGETS runs were repeated without the method cache; "
            f"{len(st['unstable'])} differed ({', '.join(st['unstable']) or 'none'}).", ""]
    pr = fx["corruption_probe"]
    out += ["### Corruption probe (verifier)", "",
            "For every REACHABLE entry of a TARGETS verdict, its first path was corrupted and the verifier run again "
            "on the pre-verifier evidence. WRONG_LINE moves one call site down a line; EDGE_NOT_IN_GRAPH inserts a "
            "fabricated hop through `vulnlib.Safe`; BROKEN_CHAIN drops an inner edge (or renames the last callee).", ""]
    out += _table(["corruption", "paths", "rejected (CANT_DETERMINE / VERIFIER_REJECTED)"],
                  [[k, v["total"], v["rejected"]] for k, v in sorted(pr["by_corruption"].items())])
    checks = {}
    for r in pr["rows"]:
        for c in r["failed_checks"]:
            checks[c] = checks.get(c, 0) + 1
    out += ["", f"Checks that fired across the {pr['total']} corrupted paths: {_counts(checks)}.", ""]
    if fx.get("schema_problems"):
        out += [f"Schema problems: {len(fx['schema_problems'])} verdicts violated the schema.", ""]
    else:
        out += ["Every fixture verdict validated against `schemas/verdict.schema.json`.", ""]
    return out


def render_real(doc: dict[str, Any], title: str, note: str) -> list[str]:
    s = doc["summary"]
    out = [title, ""] + _env(doc) + ["", note, ""]
    out += [f"- Cases: {s['cases']}; evidence status: {_counts(s['evidence_status'])}; harness errors: {s['harness_errors']}.",
            f"- Preparation of the vulnerable-side tree (`git archive` + `go mod tidy -e`): {_counts(s['prep_status'])}.",
            f"- Triaged (prepared and run): {s['triaged']}; mode: {_counts(s['mode'])}; mode reason: {_counts(s['mode_reason'])}.",
            f"- Main packages analysed: {s['mains_analysed']} (at most {doc.get('max_mains')} per case); cases with main "
            f"packages over the limit: {s['cases_with_mains_skipped']}; cases with no main package: {s['cases_no_main']}; "
            f"cases where every main package failed to load or build: {s['cases_all_mains_load_failed']}.",
            f"- Target symbols analysed: {s['symbols']}; not analysed: {_counts(s['not_covered'])}; Mode 1 symbols that "
            f"are context-only: {s['context_only_symbols']}.", ""]
    out += ["### Verdict distribution (not accuracy)", ""]
    rows = [[v, s["pre_policy_verdict"].get(v, 0), s["verdict"].get(v, 0)] for v in VERDICTS]
    out += _table(["verdict", "before policy", "final"], rows)
    out += ["", f"CANT_DETERMINE reasons (final): {_counts(s['reason_codes'])}.",
            f"CANT_DETERMINE reasons (before policy): {_counts(s['pre_policy_reason_codes'])}.", ""]
    out += [f"- Per (symbol, main package) entries: {_counts(s['entry_results'])}.",
            f"- Method result pairs (VTA + linker): {_counts(s['method_pairs'])}.",
            f"- Method error codes: {_counts(s['method_errors'])}.",
            f"- Verifier: {s['verification']['checks_run']} checks; {s['verification']['downgraded_entries']} entries "
            f"downgraded in {s['verification']['cases_with_downgrade']} cases; failed checks by kind: "
            f"{_counts(s['verification']['failed_by_kind'])}.",
            f"- REACHABLE verdicts without a verified path: {s['reachable_without_verified_path']}; DYNAMIC edges on "
            f"verified paths: {s['dynamic_edges_on_verified']}.",
            f"- Go toolchain reported by the helper: {_counts(s['go_versions'])}.", ""]
    ref = s["reference"]
    out += ["### Curated reference (consistency, not correctness)", "",
            f"The same app analysed with the advisory's curated core symbols as targets: {ref['cases']} cases; reference "
            f"verdicts: {_counts(ref['verdict'])}. Cases whose analysed symbols include a curated core symbol: "
            f"{ref['gold_analysed']}.", ""]
    out += _table(["pipeline (before policy) | reference", "cases"], [[k, v] for k, v in sorted(ref["pairs_pre_policy"].items())])
    out += [""]
    if "without_rclone_cluster" in s:
        w = s["without_rclone_cluster"]
        ci = s.get("pre_policy_reachable_share_cluster_ci") or {}
        out += ["### D4 clustering (CP3 review finding 1)", "",
                f"- Without the rclone pseudo-replicate cluster: {w['triaged']} triaged; before policy {_counts(w['pre_policy_verdict'])}; "
                f"final {_counts(w['verdict'])}.",
                f"- Distinct release ranges per verdict before policy: {_counts(s['distinct_ranges'])}.",
                f"- Share REACHABLE before policy, cluster bootstrap: {ci.get('mean', 0):.3f} [{ci.get('ci_low', 0):.3f}, "
                f"{ci.get('ci_high', 0):.3f}] over {ci.get('n', 0)} cases in {ci.get('n_clusters', 0)} clusters.", ""]
    fb = s["fallbacks"]
    out += ["### Cost and fallbacks", "",
            f"- Seconds per case (preparation + triage + reference): {_fmt_secs(s['seconds'])}.",
            f"- Seconds per triage run: {_fmt_secs(s['triage_seconds'])}; preparation: {_fmt_secs(s['prep_seconds'])}.",
            f"- Fallbacks: Mode 1 -> Mode 2 {fb['mode_fix_to_release']}; retriever {_counts(fb['retriever'])}; "
            f"synthesised go.mod {fb['synthesized_go_mod']}; vendor directory set aside {fb['vendor_dropped']}; "
            f"main packages over the limit {fb['mains_over_limit']}.", ""]
    return out


def _fmt_secs(s: dict[str, Any]) -> str:
    if not s or not s.get("n"):
        return "n/a"
    return f"p50 {s['p50']}, p95 {s['p95']}, max {s['max']} (n {s['n']}, total {s['total']})"


def render_cp7_doc(d: Path, source: str) -> str:
    fx, d1, d4 = _load(d, "fixtures.json"), _load(d, "d1.json"), _load(d, "d4.json")
    out = ["# CP7 triage results", "", f"Generated by `python -m vulntrace results render --doc cp7 --input {source}` from "
           "the files in that directory. Do not edit by hand.", "", "## Headline", "", HEADLINE, "",
           "(This sentence was fixed in `eval/triage_report.py` before any result existed.)", "",
           "Reachability only: every verdict here says whether a function can be reached in the call graph from "
           "`main` or `init`, never whether a vulnerability can be exploited.", ""]
    if fx:
        out += render_fixtures(fx)
    else:
        out += ["## 1. Fixtures", "", "Not run (no fixtures.json).", ""]
    not_acc = ("These cases have no reachability truth: the app is the vulnerable module itself, at its vulnerable "
               "commit, with its own main packages as entry points. The numbers below are distributions, coverage and "
               "reasons, not accuracy.")
    out += render_real(d1, "## 2. D1 (Mode 1 on real fix commits)", not_acc) if d1 else ["## 2. D1", "", "Not run.", ""]
    out += render_real(d4, "## 3. D4 (Mode 2 on real release ranges)", not_acc) if d4 else ["## 3. D4", "", "Not run.", ""]
    pol = decide_mode2_policy(fx["rows"] if fx else [], d4["rows"] if d4 else None)
    out += ["## 4. Mode 2 NOT_REACHABLE policy (decided by code from the numbers above)", "", f"Rule: {POLICY_RULE_TEXT}", ""]
    out += [f"- {k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}" for k, v in pol["inputs"].items()
            if not k.endswith("_ids")]
    out += [f"- check {k}: {'pass' if v else 'FAIL'}" for k, v in pol["checks"].items()]
    out += ["", f"**Decision: {pol['decision']}.**", ""]
    return "\n".join(out).rstrip() + "\n"
