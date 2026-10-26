"""JSON action protocol (CP6): the model emits one JSON object per turn, code parses and validates it.

No provider tool calling: 7-8B local models are unreliable at it (CP5 review). An action is

    {"tool": "<name>", "args": {...}}

with exactly these two keys. `parse_action` checks the shape and the argument types of the named
tool and never repairs anything (no stripping of markdown fences, no guessing of a tool name);
a failure is a list of `Problem`s that the graph shows the model once (`agent_repair_v1`).

`submit_answer` has a second, content-level check (`check_answer`): IDs must be in the case's
candidate pool, 1..`max_ids` distinct IDs, and the cited evidence must be IDs or commit SHAs that
appeared in the trace. A rejected answer gets one retry per run; a second rejection is
`INVALID_ANSWER`.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from vulntrace.llm.prompts import one_line

SEARCH_CODE, READ_FUNCTION, SEARCH_COMMITS, SHOW_COMMIT = "search_code", "read_function", "search_commits", "show_commit"
CALLERS, CALLEES, SUBMIT = "callers", "callees", "submit_answer"
BASE_TOOLS = (SEARCH_CODE, READ_FUNCTION, SEARCH_COMMITS, SHOW_COMMIT, SUBMIT)
GRAPH_TOOLS = (CALLERS, CALLEES)

SEARCH_K_DEFAULT, SEARCH_K_MAX = 10, 20
MAX_EVIDENCE = 10
MIN_SHA_PREFIX = 7

# name -> {arg: (type, required)}
ARG_SPECS: dict[str, dict[str, tuple[type, bool]]] = {
    SEARCH_CODE: {"query": (str, True), "k": (int, False)},
    READ_FUNCTION: {"candidate_id": (str, True)},
    SEARCH_COMMITS: {"query": (str, True)},
    SHOW_COMMIT: {"sha": (str, True)},
    CALLERS: {"candidate_id": (str, True)},
    CALLEES: {"candidate_id": (str, True)},
    SUBMIT: {"candidate_ids": (list, False), "evidence": (list, False), "abstain": (bool, False)},
}


@dataclass(frozen=True)
class Problem:
    code: str       # fixed vocabulary (safe to commit)
    message: str    # shown to the model in the repair turn


@dataclass(frozen=True)
class Action:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        """Identity of a call for loop detection: tool plus canonical arguments (query text
        compared case- and whitespace-insensitively)."""
        norm = {k: (" ".join(v.lower().split()) if isinstance(v, str) else v) for k, v in self.args.items()}
        if self.tool == SEARCH_CODE:
            norm.setdefault("k", SEARCH_K_DEFAULT)
        return self.tool + " " + json.dumps(norm, sort_keys=True)

    def as_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "args": self.args}


def _type_ok(value: Any, typ: type) -> bool:
    if typ is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, typ)


def parse_action(text: str, tools: Iterable[str]) -> tuple[Action | None, list[Problem]]:
    tools = tuple(tools)
    if not text.strip():
        return None, [Problem("EMPTY_OUTPUT", "the reply was empty")]
    try:
        obj = json.loads(text)
    except ValueError as exc:
        return None, [Problem("NOT_JSON", f"the reply is not valid JSON ({one_line(str(exc), 80)})")]
    if not isinstance(obj, dict):
        return None, [Problem("NOT_OBJECT", "the reply must be one JSON object")]
    if set(obj) != {"tool", "args"}:
        return None, [Problem("BAD_KEYS", 'the object must have exactly the keys "tool" and "args"')]
    tool, args = obj["tool"], obj["args"]
    if not isinstance(tool, str) or tool not in tools:
        return None, [Problem("UNKNOWN_TOOL", f"{one_line(str(tool), 40)!r} is not one of the available tools "
                                              f"({', '.join(tools)})")]
    if not isinstance(args, dict):
        return None, [Problem("ARGS_NOT_OBJECT", '"args" must be a JSON object')]
    spec = ARG_SPECS[tool]
    problems = []
    extra = sorted(set(args) - set(spec))
    if extra:
        problems.append(Problem("UNKNOWN_ARG", f"{tool} does not take {', '.join(repr(one_line(x, 30)) for x in extra[:5])}"))
    for name, (typ, required) in spec.items():
        if name not in args:
            if required:
                problems.append(Problem("MISSING_ARG", f"{tool} needs {name!r}"))
        elif not _type_ok(args[name], typ):
            problems.append(Problem("ARG_TYPE", f"{name!r} of {tool} must be a {typ.__name__}"))
    if problems:
        return None, problems
    problems += _value_problems(tool, args)
    if problems:
        return None, problems
    return Action(tool, dict(args)), []


def _value_problems(tool: str, args: dict[str, Any]) -> list[Problem]:
    out = []
    if tool in (SEARCH_CODE, SEARCH_COMMITS) and not args["query"].strip():
        out.append(Problem("EMPTY_QUERY", f"the query of {tool} is empty"))
    if tool == SEARCH_CODE and "k" in args and not 1 <= args["k"] <= SEARCH_K_MAX:
        out.append(Problem("BAD_K", f"k must be between 1 and {SEARCH_K_MAX}"))
    if tool == SUBMIT:
        ids, ev, abstain = args.get("candidate_ids"), args.get("evidence"), args.get("abstain")
        if abstain is True:
            if ids or ev:
                out.append(Problem("ABSTAIN_WITH_ANSWER", 'with "abstain": true give no candidate_ids and no evidence'))
        else:
            if ids is None or ev is None:
                out.append(Problem("MISSING_ARG", 'submit_answer needs "candidate_ids" and "evidence" '
                                                  '(or {"abstain": true})'))
            for name, value in (("candidate_ids", ids), ("evidence", ev)):
                if value is not None and not all(isinstance(x, str) for x in value):
                    out.append(Problem("ARG_TYPE", f"{name!r} must be a list of strings"))
    return out


@dataclass(frozen=True)
class Answer:
    candidate_ids: tuple[str, ...]
    evidence: tuple[str, ...]
    abstain: bool


def check_answer(action: Action, pool: set[str] | frozenset[str], max_ids: int, seen_candidates: set[str],
                 seen_commits: Iterable[str]) -> tuple[Answer | None, list[Problem]]:
    """Content check of a well-formed `submit_answer` action."""
    a = action.args
    if a.get("abstain") is True:
        return Answer((), (), True), []
    ids, ev = list(a["candidate_ids"]), list(a["evidence"])
    problems = []
    outside = [x for x in ids if x not in pool]
    if outside:
        problems.append(Problem("ID_NOT_IN_POOL", "these IDs are not in the candidate pool: "
                                + ", ".join(repr(one_line(x, 40)) for x in outside[:5])))
    if not ids:
        problems.append(Problem("NO_IDS", f"give 1 to {max_ids} candidate IDs, or abstain"))
    if len(ids) > max_ids:
        problems.append(Problem("TOO_MANY_IDS", f"at most {max_ids} candidate IDs, got {len(ids)}"))
    if len(set(ids)) != len(ids):
        problems.append(Problem("DUPLICATE_ID", "an ID appears more than once"))
    if not ev:
        problems.append(Problem("NO_EVIDENCE", "cite at least one candidate ID or commit SHA from the tool outputs"))
    if len(ev) > MAX_EVIDENCE:
        problems.append(Problem("TOO_MUCH_EVIDENCE", f"cite at most {MAX_EVIDENCE} items"))
    commits = list(seen_commits)
    unseen = [x for x in ev if not (x in seen_candidates or _sha_seen(x, commits))]
    if unseen:
        problems.append(Problem("EVIDENCE_NOT_SEEN", "this evidence did not appear in any tool output: "
                                + ", ".join(repr(one_line(x, 40)) for x in unseen[:5])))
    if problems:
        return None, problems
    return Answer(tuple(ids), tuple(ev), False), []


def _sha_seen(ref: str, commits: list[str]) -> bool:
    ref = ref.strip().lower()
    return len(ref) >= MIN_SHA_PREFIX and any(c.lower().startswith(ref) for c in commits)
