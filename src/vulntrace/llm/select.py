"""Closed-set selection: validation in code, one retry, honest INVALID (CP5 deliverable 3).

The model answers `{"selected": [ids], "abstain": bool}`. This module decides whether that is
acceptable:

- the text must parse as one JSON object with exactly the keys `selected` and `abstain`;
- `selected` is a list of distinct strings, each in the candidate list, at most N long (N is a
  constant of the prompt: 5 in Mode 1, 3 in Mode 2);
- `abstain` is a boolean; `abstain: true` goes with an empty list, `abstain: false` with a
  non-empty one.

If the first answer fails, the model gets exactly **one** more attempt with the reasons shown.
Both attempts are recorded. A second failure is `INVALID`: nothing is repaired (no stripping of
markdown fences, no dropping of unknown IDs) and nothing is dropped from the counts. Free-text
symbol names in the answer are never interpreted.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from vulntrace.llm.prompts import Prompt, one_line, retry_message
from vulntrace.models.llm import LLMClient, LLMError, LLMResponse, LLMSettings

STATUS_VALID, STATUS_INVALID, STATUS_ERROR = "VALID", "INVALID", "ERROR"
SELECTION_KEYS = ("abstain", "selected")

SELECTION_SETTINGS = LLMSettings(temperature=0.0, seed=7, max_tokens=300, json_mode=True)


@dataclass(frozen=True)
class Problem:
    code: str       # fixed vocabulary, safe to commit
    message: str    # shown to the model on the retry; may quote (a cut of) its own answer


@dataclass(frozen=True)
class Parsed:
    selected: tuple[str, ...]
    abstain: bool


def validate_output(text: str, candidate_ids: tuple[str, ...] | list[str], max_selected: int) -> tuple[Parsed | None, list[Problem]]:
    """(parsed answer, []) if acceptable, else (None, problems). Never repairs."""
    if not text.strip():
        return None, [Problem("EMPTY_OUTPUT", "the answer was empty")]
    try:
        obj = json.loads(text)
    except ValueError as exc:
        return None, [Problem("NOT_JSON", f"the answer is not valid JSON ({one_line(str(exc), 80)})")]
    if not isinstance(obj, dict):
        return None, [Problem("NOT_OBJECT", "the answer must be one JSON object")]
    problems: list[Problem] = []
    if tuple(sorted(obj)) != SELECTION_KEYS:
        problems.append(Problem("BAD_KEYS", 'the object must have exactly the keys "selected" and "abstain"'))
    sel, abstain = obj.get("selected"), obj.get("abstain")
    if not isinstance(abstain, bool):
        problems.append(Problem("ABSTAIN_NOT_BOOL", '"abstain" must be true or false'))
    if not isinstance(sel, list) or not all(isinstance(x, str) for x in sel):
        problems.append(Problem("SELECTED_NOT_LIST", '"selected" must be a list of candidate ID strings'))
    if problems:
        return None, problems
    allowed = set(candidate_ids)
    outside = [x for x in sel if x not in allowed]
    if outside:
        problems.append(Problem("ID_NOT_IN_SET", "these IDs are not in the candidate list: "
                                + ", ".join(repr(one_line(x, 40)) for x in outside[:5])))
    if len(set(sel)) != len(sel):
        problems.append(Problem("DUPLICATE_ID", "an ID appears more than once"))
    if len(sel) > max_selected:
        problems.append(Problem("TOO_MANY", f"at most {max_selected} IDs may be selected, got {len(sel)}"))
    if abstain and sel:
        problems.append(Problem("ABSTAIN_WITH_SELECTION", '"abstain" is true but "selected" is not empty'))
    if not abstain and not sel:
        problems.append(Problem("EMPTY_WITHOUT_ABSTAIN", '"selected" is empty but "abstain" is false'))
    if problems:
        return None, problems
    return Parsed(tuple(sel), abstain), []


@dataclass
class Attempt:
    valid: bool
    problem_codes: list[str]
    provenance: dict[str, Any]

    def row(self) -> dict[str, Any]:
        p = self.provenance
        return {"valid": self.valid, "problems": self.problem_codes, "input_tokens": p["input_tokens"],
                "output_tokens": p["output_tokens"], "latency_s": p["latency_s"], "cached": p["cached"],
                "finish_reason": p["finish_reason"], "response_sha256": p["response_sha256"]}


@dataclass
class SelectionResult:
    status: str                       # VALID | INVALID | ERROR
    selected: tuple[str, ...] = ()
    abstain: bool = False
    attempts: list[Attempt] = field(default_factory=list)
    error: str | None = None          # LLMError code when status == ERROR

    @property
    def retried(self) -> bool:
        return len(self.attempts) > 1

    @property
    def input_tokens(self) -> int:
        return sum(a.provenance["input_tokens"] or 0 for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.provenance["output_tokens"] or 0 for a in self.attempts)

    @property
    def latency_s(self) -> float:
        return sum(a.provenance["latency_s"] for a in self.attempts)

    def row(self) -> dict[str, Any]:
        """Committable record: parsed answer, validity, tokens, latencies. No prompt, no raw text."""
        return {"status": self.status, "selected": list(self.selected), "abstain": self.abstain,
                "retried": self.retried, "error": self.error, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "latency_s": round(self.latency_s, 3),
                "attempts": [a.row() for a in self.attempts]}


def select(client: LLMClient, prompt: Prompt, settings: LLMSettings = SELECTION_SETTINGS) -> SelectionResult:
    """Run one closed-set selection with at most one retry. An `LLMError` (server problem) gives
    status ERROR; it is not an answer and is counted separately."""
    messages = prompt.messages()
    attempts: list[Attempt] = []
    parsed, problems = None, []
    for attempt_no in range(2):
        try:
            resp: LLMResponse = client.complete(messages, settings)
        except LLMError as exc:
            return SelectionResult(STATUS_ERROR, attempts=attempts, error=exc.code)
        parsed, problems = validate_output(resp.text, prompt.candidate_ids, prompt.max_selected)
        attempts.append(Attempt(parsed is not None, [p.code for p in problems], resp.provenance()))
        if parsed is not None:
            return SelectionResult(STATUS_VALID, parsed.selected, parsed.abstain, attempts)
        if attempt_no == 0:
            messages = messages + [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": retry_message("; ".join(p.message for p in problems),
                                                          prompt.candidate_ids, prompt.max_selected)}]
    return SelectionResult(STATUS_INVALID, (), False, attempts)
