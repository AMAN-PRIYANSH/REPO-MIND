"""CP8: the results summary generator. `python -m vulntrace results summary` must reproduce the committed
`docs/results/SUMMARY.md`, `docs/results/summary.json` and the README key-results table exactly from the committed result files,
and its numbers must equal the ones the per-checkpoint results documents print."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from vulntrace.eval import summary as S
from vulntrace.paths import REPO_ROOT

RESULTS = REPO_ROOT / "docs" / "results"

# Rows that exist only in the summary: the pair they compare is not a table in the CP4 results document. They are still computed by the
# same committed code (retrieval_report.Summaries.paired_diff) from the committed run files.
NOT_IN_RESULTS_DOC = {"cp4.d_mrr.dense_code_vs_dense", "cp4.d_mrr.commits_hybrid", "cp4.d_mrr.commits_bm25", "cp4.d_mrr.idmask_hybrid"}
DOC_OF_SECTION = {"cp4": "CP4_RETRIEVAL_RESULTS.md", "cp5": "CP5_LLM_RESULTS.md", "cp5b": "CP5B_LIFTING_RESULTS.md",
                  "cp6": "CP6_AGENT_RESULTS.md"}


@pytest.fixture(scope="module")
def built():
    return S.build_summary()


def test_summary_files_are_up_to_date():
    """Acceptance 1: regenerating gives exactly the committed SUMMARY.md, summary.json and README table."""
    for rel, text in S.expected_files().items():
        committed = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert committed == text, f"{rel} is out of date: run `python -m vulntrace results summary`"


def test_check_flag_passes_on_this_checkout(capsys):
    class Args:
        check = True
        root = None

    assert S.cmd_summary(Args()) == 0


def test_check_flag_detects_a_stale_file(tmp_path, monkeypatch):
    files = S.expected_files()
    stale = {p: (t + "x" if p.name == "SUMMARY.md" else t) for p, t in files.items()}
    root = tmp_path
    for p, t in stale.items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(t, encoding="utf-8")
    monkeypatch.setattr(S, "expected_files", lambda r=None: files)

    class Args:
        check = True
        root = str(tmp_path)

    assert S.cmd_summary(Args()) == 1


def test_every_source_hash_is_current():
    committed = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    assert committed["sources"], "summary.json lists no sources"
    for rel, digest in committed["sources"].items():
        assert hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest() == digest, rel


def test_every_row_names_existing_sources_and_has_unique_id(built):
    ids = []
    for sec in built["sections"]:
        for r in sec["rows"]:
            ids.append(r["id"])
            assert r["source"], r["id"]
            for s in r["source"]:
                assert (REPO_ROOT / s).exists(), f"{r['id']}: {s}"
    assert len(ids) == len(set(ids))


def test_json_has_the_experiments_the_spec_lists(built):
    assert [s["id"] for s in built["sections"]] == ["datasets", "cp4", "cp5", "cp5b", "cp6", "cp7", "cp7b"]
    rows = S.index_rows(built)
    for rid in ("cp4.mrr.hybrid", "cp5.e1.llama3.1-8b.d_recall", "cp5.s1.llama3.1-8b.k10.d_anyhit", "cp5.hyde.qwen2.5-coder-7b.d_mrr",
                "cp5b.coverage", "cp6.qwen2.5-coder-7b.d_A2_A0", "cp7.fx.fix.false_nr", "cp7.d4.cd", "cp7b.reachable_precision"):
        assert rid in rows


def test_intervals_are_ordered_and_rates_consistent(built):
    for r in S.index_rows(built).values():
        if r.get("ci_low") is not None:
            assert r["ci_low"] <= r["ci_high"] + 1e-9, r["id"]
            if r["kind"] in ("mean", "delta"):
                assert r["ci_low"] - 1e-9 <= r["value"] <= r["ci_high"] + 1e-9 or r["kind"] == "delta", r["id"]
        if r["kind"] == "rate":
            assert 0 <= r["k"] <= r["n"], r["id"]
            assert abs(r["value"] - r["k"] / r["n"]) < 1e-9
        if r["kind"] == "count":
            assert 0 <= r["k"] <= r["n"], r["id"]


def test_numbers_equal_those_printed_in_the_results_documents(built):
    """The summary uses the same statistics code as the renderers; a headline number must equal the document's."""
    for sec in built["sections"]:
        if sec["id"] not in DOC_OF_SECTION:
            continue
        text = (RESULTS / DOC_OF_SECTION[sec["id"]]).read_text(encoding="utf-8")
        for r in sec["rows"]:
            if r["kind"] in ("mean", "delta") and r["id"] not in NOT_IN_RESULTS_DOC:
                cell = f"{r['value']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
                assert cell in text, f"{r['id']}: {cell} is not in {DOC_OF_SECTION[sec['id']]}"


def test_counts_and_rates_equal_those_printed_in_the_triage_documents(built):
    cp7 = (RESULTS / "CP7_TRIAGE_RESULTS.md").read_text(encoding="utf-8")
    cp7b = (RESULTS / "CP7B_REAL_APPS_RESULTS.md").read_text(encoding="utf-8")
    for r in S.index_rows(built).values():
        if r["id"].startswith("cp7b.") and r["kind"] == "rate":
            assert f"{r['k']}/{r['n']} = {r['value']:.2f} [{r['ci_low']:.2f}, {r['ci_high']:.2f}]" in cp7b, r["id"]
        if r["id"].startswith("cp7.fx.") and r["kind"] == "rate":
            assert f"{r['value']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}] ({r['k']}/{r['n']})" in cp7, r["id"]
    rows = S.index_rows(built)
    for rid, doc, pat in (("cp7b.false_nr", cp7b, r"adjudicated 4 of 4 NOT_REACHABLE verdicts|Adjudicated 4 of 4 NOT_REACHABLE verdicts"),
                          ("cp7b.govulncheck_disagree", cp7b, r"'DISAGREE': 2"), ("cp7b.cd", cp7b, r"CANT\\_DETERMINE \| 3")):
        assert re.search(pat, doc), rid
    assert f"{rows['cp7.d4.cd']['k']} of" in cp7 or str(rows["cp7.d4.cd"]["k"]) in cp7


def test_summary_markdown_links_resolve():
    text = (RESULTS / "SUMMARY.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)#]+)\)", text)
    assert links
    for link in links:
        assert (RESULTS / link).exists(), link


def test_readme_table_is_the_generated_one(built):
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    block = readme.split(S.README_BEGIN, 1)[1].split(S.README_END, 1)[0].strip("\n")
    assert block == S.key_results_markdown(built)


def test_update_readme_requires_markers():
    with pytest.raises(ValueError):
        S.update_readme("no markers here", {"sections": []})


def test_values_are_not_pre_rounded_in_memory(built):
    """A double rounding (4 decimals, then 3) once printed 0.570 where the CP5 document prints 0.569. Rows keep the raw float; only the JSON
    file is rounded (once). The document comparison above would catch a regression; this pins the mechanism."""
    r = S.index_rows(built)["cp5.e1.llama3.1-8b.recall"]
    assert r["value"] != round(r["value"], 4)
    written = json.loads(S.dumps(built))
    assert S.index_rows(written)["cp5.e1.llama3.1-8b.recall"]["value"] == round(r["value"], S.JSON_DECIMALS)


def test_hyde_comparison_counts_equal_those_printed_in_the_cp5_document(built):
    text = (RESULTS / "CP5_LLM_RESULTS.md").read_text(encoding="utf-8")
    found = 0
    for r in S.index_rows(built).values():
        if r["id"].startswith("cp5.hyde.") and r["id"].endswith(".excl"):
            alias = r["id"][len("cp5.hyde."):-len(".excl")]
            assert f"`{alias}` has {r['n']} comparisons against `query`" in text
            assert f"{r['k']} of the {r['n']} MRR intervals exclude 0" in text
            found += 1
    assert found == 2
