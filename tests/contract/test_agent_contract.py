"""CP6 contract tests: tool schemas (JSON schema = protocol code = system prompt = interfaces doc),
trace schema, and the committed result-row schema (no prompt, raw reply or code text can pass)."""

import json
import re

import pytest

pytest.importorskip("langgraph", reason="the agent needs the [agent] extra (langgraph); CI installs it")

from vulntrace.agent import budget as B  # noqa: E402
from vulntrace.agent import fakes as AF  # noqa: E402
from vulntrace.agent import graph as G  # noqa: E402
from vulntrace.agent import prompts as AP  # noqa: E402
from vulntrace.agent import protocol as P  # noqa: E402
from vulntrace.models.fakes import SequenceLLMClient, action  # noqa: E402
from vulntrace.paths import REPO_ROOT  # noqa: E402
from vulntrace.schemas import load_schema, validation_errors  # noqa: E402


def _schema_args():
    out = {}
    for branch in load_schema("agent_action")["oneOf"]:
        tool = branch["properties"]["tool"]["const"]
        args = branch["properties"]["args"]
        variants = args.get("oneOf", [args])
        out[tool] = {"props": set().union(*(v["properties"] for v in variants)),
                     "required": set().union(*(v.get("required", []) for v in variants))}
    return out


def test_action_schema_matches_the_protocol_code():
    schema = _schema_args()
    assert set(schema) == set(P.ARG_SPECS) == set(P.BASE_TOOLS + P.GRAPH_TOOLS)
    for tool, spec in P.ARG_SPECS.items():
        assert schema[tool]["props"] == set(spec), tool
        if tool != P.SUBMIT:   # submit's required set depends on abstain (two schema branches)
            assert schema[tool]["required"] == {a for a, (_t, req) in spec.items() if req}, tool


@pytest.mark.parametrize("text, valid", [
    (action("search_code", query="x", k=5), True), (action("search_code", query="x", k=50), False),
    (action("read_function", candidate_id="r1"), True), (action("read_function", id="r1"), False),
    (action("show_commit", sha="abcdef1"), True), (action("callers", candidate_id="r2"), True),
    (action("submit_answer", candidate_ids=["r1"], evidence=["r1"]), True),
    (action("submit_answer", abstain=True), True), (action("submit_answer", candidate_ids=["r1"]), False),
    ('{"tool": "search_code", "args": {"query": "x"}, "why": "..."}', False),
])
def test_schema_and_parser_agree(text, valid):
    obj = json.loads(text)
    by_schema = not validation_errors("agent_action", obj)
    parsed, _problems = P.parse_action(text, P.BASE_TOOLS[:-1] + P.GRAPH_TOOLS + (P.SUBMIT,))
    assert by_schema is valid and (parsed is not None) is valid


def test_system_prompt_documents_every_tool_and_argument():
    base = AP.system_message(8, 3, graph_tools=False)
    full = AP.system_message(8, 3, graph_tools=True)
    for tool, spec in P.ARG_SPECS.items():
        text = full
        assert f"- {tool}, args" in text or (tool == P.SUBMIT and "submit_answer" in text), tool
        for arg in spec:
            assert f'"{arg}"' in text, (tool, arg)
        assert (f"- {tool}, args" in base) == (tool not in P.GRAPH_TOOLS)


def test_interfaces_doc_lists_every_tool():
    doc = (REPO_ROOT / "docs" / "design" / "INTERFACES_AND_CONTRACTS.md").read_text(encoding="utf-8")
    section = doc.split("### Agent tools (CP6)", 1)[1].split("###", 1)[0]
    for tool in P.ARG_SPECS:
        assert re.search(rf"`{tool}`", section), tool


def _trace(replies, **kw):
    return G.run_agent(AF.fake_world(), SequenceLLMClient(replies, **kw), G.AgentConfig("A3", True))


@pytest.mark.parametrize("replies", [
    [action("read_function", candidate_id="r1"), action("submit_answer", candidate_ids=["r1"], evidence=["r1"])],
    ["nope", "nope"],
    [action("submit_answer", candidate_ids=["x"], evidence=["r1"])] * 2,
    [action("read_function", candidate_id="r1")] * 3,
    [action("callers", candidate_id="r1"), action("submit_answer", abstain=True)],
    [action("search_code", query=f"q{i}") for i in range(8)],
])
def test_traces_validate_against_the_trace_schema(replies):
    t = _trace(replies)
    assert validation_errors("agent_trace", json.loads(json.dumps(t))) == []


def test_trace_never_holds_prompt_or_tool_output_text():
    t = _trace([action("read_function", candidate_id="r1"), action("submit_answer", candidate_ids=["r1"], evidence=["r1"])])
    text = json.dumps(t)
    assert "filepath.Clean" not in text and "cleanPath does not reject" not in text and "<<<BEGIN" not in text


def test_committed_row_schema_rejects_text_fields():
    from vulntrace.eval import agent_eval

    class Case:
        case_id, created, cluster_key = "GO-1", None, "k"
        candidate_ids, gold_core, gold_core_derived = ["r1", "r2"], {"r1"}, {"r1"}

    t = _trace([action("read_function", candidate_id="r1"), action("submit_answer", candidate_ids=["r1"], evidence=["r1"])])
    row = agent_eval.row(Case, t, ["r1", "r2"])
    assert validation_errors("agent_result_row", row) == []
    assert validation_errors("agent_result_row", agent_eval.row(Case, None, [])) == []
    assert validation_errors("agent_result_row", {**row, "raw_response": "x"})   # unknown keys are rejected
    assert B.NOT_RUN in load_schema("agent_result_row")["properties"]["stop_reason"]["enum"]
