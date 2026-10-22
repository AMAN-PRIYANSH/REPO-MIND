"""HyDE: a hypothetical function written from the advisory text, used only as a retrieval query
(CP5 deliverable 4).

The model sees the advisory summary and details and nothing else (`QueryInput`: the same
leakage-safe input the plain query uses). Its output is one short Go function as plain text,
cut at `HYDE_CHAR_CAP` characters. The text is a *query*: it is never shown as evidence and is
never part of any prompt that asks for a decision.

Variants: `query` (the original query only, = CP4), `query+hyde` (original query, a blank line,
then the hypothetical), `hyde-only` (the hypothetical alone). An empty or failed generation is
counted (`empty`, `error`) and gives an empty hypothetical: `query+hyde` then equals `query`, and
`hyde-only` has an empty query whose ties the retrievers break by their seeded random order.
"""

from dataclasses import dataclass
from string import Template
from typing import Any

from vulntrace.llm.prompts import (ADVISORY_DETAILS_CHAR_CAP, HYDE_PROMPT, HYDE_SYSTEM_PROMPT, escape_untrusted, one_line,
                                   cut, template_sha256, template_text)
from vulntrace.models.llm import LLMClient, LLMError, LLMSettings
from vulntrace.retrieval.query import QueryInput

HYDE_CHAR_CAP = 1200
HYDE_SETTINGS = LLMSettings(temperature=0.0, seed=7, max_tokens=400, json_mode=False)

VARIANT_QUERY, VARIANT_QUERY_HYDE, VARIANT_HYDE_ONLY = "query", "query+hyde", "hyde-only"
HYDE_VARIANTS = (VARIANT_QUERY, VARIANT_QUERY_HYDE, VARIANT_HYDE_ONLY)


def prompt_version() -> dict[str, str]:
    return {"version": HYDE_PROMPT, "sha256": template_sha256(HYDE_SYSTEM_PROMPT, HYDE_PROMPT)}


def build_messages(advisory: QueryInput) -> list[dict[str, str]]:
    if not isinstance(advisory, QueryInput):
        raise TypeError("HyDE takes a QueryInput (summary and details only), not a case")
    summary, _ = escape_untrusted(one_line(advisory.summary, 500))
    details, _ = escape_untrusted(cut(advisory.details.strip(), ADVISORY_DETAILS_CHAR_CAP)[0])
    user = Template(template_text(HYDE_PROMPT)).substitute(summary=summary, details=details or "(none)")
    return [{"role": "system", "content": template_text(HYDE_SYSTEM_PROMPT).strip()}, {"role": "user", "content": user}]


def clean_hypothetical(text: str) -> tuple[str, bool]:
    """(text, truncated). Formatting only: one surrounding markdown code fence is removed, then
    the text is stripped and cut at the cap. Nothing else is changed."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    t = t.strip()
    return (t[:HYDE_CHAR_CAP], True) if len(t) > HYDE_CHAR_CAP else (t, False)


@dataclass
class HydeResult:
    text: str
    truncated: bool
    empty: bool
    error: str | None
    provenance: dict[str, Any]

    def row(self) -> dict[str, Any]:
        """Committable: lengths and flags only, not the hypothetical text."""
        p = self.provenance
        return {"chars": len(self.text), "truncated": self.truncated, "empty": self.empty, "error": self.error,
                "input_tokens": p.get("input_tokens"), "output_tokens": p.get("output_tokens"),
                "latency_s": p.get("latency_s"), "cached": p.get("cached"), "response_sha256": p.get("response_sha256")}


def generate(client: LLMClient, advisory: QueryInput, settings: LLMSettings = HYDE_SETTINGS) -> HydeResult:
    try:
        resp = client.complete(build_messages(advisory), settings)
    except LLMError as exc:
        return HydeResult("", False, True, exc.code, {})
    text, truncated = clean_hypothetical(resp.text)
    return HydeResult(text, truncated, not text, None, resp.provenance())


def assemble_query(variant: str, query: str, hypothetical: str) -> str:
    if variant == VARIANT_QUERY:
        return query
    if variant == VARIANT_QUERY_HYDE:
        return "\n\n".join(p for p in (query.strip(), hypothetical.strip()) if p)
    if variant == VARIANT_HYDE_ONLY:
        return hypothetical.strip()
    raise ValueError(f"unknown HyDE variant {variant!r}; expected one of {HYDE_VARIANTS}")
