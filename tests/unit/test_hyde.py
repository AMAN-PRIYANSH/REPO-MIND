import json

import pytest

from vulntrace.llm import hyde
from vulntrace.models import fakes
from vulntrace.models.llm import LLMError
from vulntrace.retrieval.query import QueryInput, query_input_from_case

from tests.unit.test_llm_prompts_select import SENTINELS, _case


def test_hyde_prompt_reads_only_summary_and_details_and_rejects_a_raw_case():
    case = _case()
    msgs = hyde.build_messages(query_input_from_case(case))
    assert case.read == {"summary", "details"}
    text = "\n".join(m["content"] for m in msgs)
    assert "Path traversal in local backend" in text
    for s in SENTINELS:
        assert s not in text
    with pytest.raises(TypeError):
        hyde.build_messages(case)  # type: ignore[arg-type]


def test_query_assembly_for_the_three_variants():
    q, h = "Path traversal", "func Move(p string) {}"
    assert hyde.assemble_query("query", q, h) == q
    assert hyde.assemble_query("query+hyde", q, h) == q + "\n\n" + h
    assert hyde.assemble_query("hyde-only", q, h) == h
    assert hyde.assemble_query("query+hyde", q, "") == q          # an empty hypothetical falls back to the query
    assert hyde.assemble_query("hyde-only", q, "  ") == ""
    with pytest.raises(ValueError):
        hyde.assemble_query("other", q, h)


def test_clean_strips_one_fence_and_caps_length():
    assert hyde.clean_hypothetical("```go\nfunc A() {}\n```") == ("func A() {}", False)
    assert hyde.clean_hypothetical("  func A() {}  ") == ("func A() {}", False)
    long, cut = hyde.clean_hypothetical("x" * (hyde.HYDE_CHAR_CAP + 5))
    assert cut and len(long) == hyde.HYDE_CHAR_CAP
    assert hyde.clean_hypothetical("```") == ("", False)


def test_generate_counts_empty_truncated_and_errors():
    adv = QueryInput("s", "d")
    ok = hyde.generate(fakes.FakeLLMClient(fallback=lambda m: "func A() {}"), adv)
    assert ok.text == "func A() {}" and not ok.empty and not ok.truncated and ok.error is None
    assert hyde.generate(fakes.FakeLLMClient(fallback=lambda m: ""), adv).empty
    assert hyde.generate(fakes.FakeLLMClient(fallback=lambda m: "y" * 5000), adv).truncated

    class Down(fakes.FakeLLMClient):
        def complete(self, *a, **k):
            raise LLMError("CONNECTION", "refused")

    err = hyde.generate(Down(), adv)
    assert err.error == "CONNECTION" and err.empty and err.text == ""


def test_row_has_lengths_not_the_text():
    r = hyde.generate(fakes.FakeLLMClient(fallback=lambda m: "func SECRETHYPOTHETICAL() {}"), QueryInput("s", ""))
    dumped = json.dumps(r.row())
    assert "SECRETHYPOTHETICAL" not in dumped and r.row()["chars"] == len(r.text)
