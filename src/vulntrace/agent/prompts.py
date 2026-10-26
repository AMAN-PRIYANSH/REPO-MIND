"""Agent prompt templates (CP6 deliverable 2): versioned text files in `agent/prompts/`, frozen
before the first real run (`FROZEN.json`, enforced by `tests/unit/test_agent_prompts_frozen.py`).

Every text the model reads comes from one of these files; code only fills placeholders:

- `agent_system_v1`: role, JSON action protocol, tool list, rules (`$graph_tools` is empty or
  the text of `agent_graph_tools_v1`, so the two arms differ only by those lines);
- `agent_task_v1`: the advisory (summary, details) and the automatic first search;
- `agent_observation_v1`: one tool output, with the steps left (`agent_last_step_v1` is added
  when one step is left);
- `agent_repeat_v1`: the output given instead of re-running an identical call;
- `agent_repair_v1`: the reply to an invalid action or a rejected answer (the only repair turn).

The advisory is read only through `QueryInput` (summary and details), as in CP4 and CP5: no fix
commit, no gold symbols, no `derived_symbols` can reach a prompt.
"""

import hashlib
from importlib import resources
from string import Template

from vulntrace.llm.prompts import ADVISORY_DETAILS_CHAR_CAP, cut, escape_untrusted, one_line
from vulntrace.retrieval.query import QueryInput

SYSTEM = "agent_system_v1"
GRAPH_TOOLS = "agent_graph_tools_v1"
TASK = "agent_task_v1"
OBSERVATION = "agent_observation_v1"
LAST_STEP = "agent_last_step_v1"
REPEAT = "agent_repeat_v1"
REPAIR = "agent_repair_v1"
ALL_TEMPLATES = (SYSTEM, GRAPH_TOOLS, TASK, OBSERVATION, LAST_STEP, REPEAT, REPAIR)
PROMPT_SET = "agent_v1"   # the name results carry; the hash below says exactly which text it was


def template_text(name: str) -> str:
    return resources.files("vulntrace.agent").joinpath("prompts", f"{name}.txt").read_text(encoding="utf-8")


def prompt_set_sha256() -> str:
    h = hashlib.sha256()
    for n in ALL_TEMPLATES:
        h.update(n.encode("utf-8") + b"\0" + template_text(n).encode("utf-8") + b"\0")
    return h.hexdigest()


def _fill(name: str, **values) -> str:
    return Template(template_text(name)).substitute(**values).strip()


def system_message(max_steps: int, max_ids: int, graph_tools: bool) -> str:
    graph = template_text(GRAPH_TOOLS).strip() + "\n" if graph_tools else ""
    return _fill(SYSTEM, max_steps=max_steps, max_ids=max_ids, graph_tools=graph)


def task_message(advisory: QueryInput, n_candidates: int, initial_search: str, max_steps: int) -> tuple[str, dict]:
    """The first user message and what was cut or escaped in it."""
    if not isinstance(advisory, QueryInput):
        raise TypeError("the agent's task message takes a QueryInput (summary and details only)")
    summary, n1 = escape_untrusted(one_line(advisory.summary, 500))
    details, was_cut = cut(advisory.details.strip(), ADVISORY_DETAILS_CHAR_CAP)
    details, n2 = escape_untrusted(details)
    text = _fill(TASK, summary=summary, details=details or "(none)", n_candidates=n_candidates,
                 initial_search=initial_search, max_steps=max_steps)
    return text, {"advisory_details_truncated": was_cut, "delimiter_escapes": n1 + n2}


def observation_message(tool: str, step: int, max_steps: int, output: str) -> str:
    left = max_steps - step
    note = (" " + template_text(LAST_STEP).strip()) if left == 1 else ""
    return _fill(OBSERVATION, tool=tool, step=step, max_steps=max_steps, output=output, steps_left=left, note=note)


def repeat_output(first_step: int) -> str:
    return _fill(REPEAT, first_step=first_step)


def repair_message(problems: str, tools: tuple[str, ...]) -> str:
    return _fill(REPAIR, problems=problems, tools=", ".join(tools))
