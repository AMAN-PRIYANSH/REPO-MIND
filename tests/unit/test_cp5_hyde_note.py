"""CP5b task 0d: each model's HyDE section states how many comparisons its tables hold, computed
from the same rows, so one borderline interval cannot read as a finding. Uses the committed bundle."""

import re

from vulntrace.eval.llm_report import render_cp5_doc
from vulntrace.paths import REPO_ROOT

CP5 = REPO_ROOT / "docs" / "results" / "cp5"


def test_every_hyde_section_states_its_comparison_count_and_it_matches_the_tables():
    doc = render_cp5_doc(CP5, "docs/results/cp5")
    sections = re.split(r"^## HyDE \(Mode 2, D4\): ", doc, flags=re.M)[1:]
    assert len(sections) == 2
    for sec in sections:
        sec = re.split(r"^## ", sec, flags=re.M)[0]
        m = re.search(r"has (\d+) comparisons against `query`.*?(\d+) of the \d+ MRR intervals exclude 0", sec, flags=re.S)
        assert m, sec[:300]
        n_cmp, n_excl = int(m.group(1)), int(m.group(2))
        rows = [ln for ln in sec.splitlines() if re.match(r"\| \S+ \| (query\+hyde|hyde-only) \|", ln)]
        assert len(rows) == n_cmp
        assert sum("(interval excludes 0)" in r and "no detectable" not in r for r in rows) == n_excl


def test_the_committed_results_document_carries_the_note():
    text = (REPO_ROOT / "docs" / "results" / "CP5_LLM_RESULTS.md").read_text(encoding="utf-8")
    assert text.count("How many comparisons this table holds") == 2
