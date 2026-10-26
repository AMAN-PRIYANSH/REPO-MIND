"""Budgets and stop reasons of one agent run (CP6 deliverable 1). Recorded in every result file.

- `max_steps`: executed actions (tool calls, and the accepted `submit_answer`). Repair turns and
  the one retry after a rejected answer are not steps; they cost tokens and time.
- `max_tool_chars`: characters of one tool output shown to the model; longer output is cut and
  says so.
- `max_total_prompt_tokens`: prompt tokens of all model calls of the case together (the server's
  count where it reports one, else an estimate). A call whose estimated prompt would cross it is
  not made.
- `max_prompt_tokens_per_call`: kept below the server's context length so that a prompt is never
  silently truncated by the server.
- `max_seconds`: the case's time budget, counted as the model time recorded for each call plus
  the measured tool time. Recorded model time is stored in the response cache, so a run resumed
  from the cache takes exactly the same budget decisions as the original run.

A budget stop scores as a miss and is counted by reason.
"""

from dataclasses import asdict, dataclass
from typing import Any

# stop reasons
SUBMITTED, ABSTAINED, INVALID_ANSWER, INVALID_ACTION = "SUBMITTED", "ABSTAINED", "INVALID_ANSWER", "INVALID_ACTION"
LOOP_DETECTED, BUDGET_EXCEEDED, ERROR, NOT_RUN = "LOOP_DETECTED", "BUDGET_EXCEEDED", "ERROR", "NOT_RUN"
STOP_REASONS = (SUBMITTED, ABSTAINED, INVALID_ANSWER, INVALID_ACTION, LOOP_DETECTED, BUDGET_EXCEEDED, ERROR, NOT_RUN)
# budget reasons
STEPS, TOKENS, CONTEXT, TIME = "STEPS", "TOKENS", "CONTEXT", "TIME"
BUDGET_REASONS = (STEPS, TOKENS, CONTEXT, TIME)

CHARS_PER_TOKEN_ESTIMATE = 3.0   # conservative for code (real tokenizers average 3-4 characters per token)


@dataclass(frozen=True)
class Budget:
    max_steps: int = 8
    max_tool_chars: int = 3000
    max_total_prompt_tokens: int = 80000
    max_prompt_tokens_per_call: int = 24000
    max_seconds: float = 600.0
    max_answer_ids: int = 3
    max_repeated_calls: int = 1   # repeats of earlier calls allowed per run (each answered with a note); the next
                                  # repeat of any earlier call stops the run (LOOP_DETECTED)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    chars = sum(len(m["content"]) for m in messages)
    return int(chars / CHARS_PER_TOKEN_ESTIMATE) + 1
