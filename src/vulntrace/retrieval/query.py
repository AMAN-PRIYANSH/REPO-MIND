"""The Mode 2 retrieval query (CP4 deliverable 1, leakage control).

The query is the advisory's summary and details only. It must never contain the fix commit,
the curated symbols, `derived_symbols`, or anything else from the evaluation's gold side. This
is enforced structurally: `build_query` accepts only a `QueryInput`, which has exactly two
fields, and `query_input_from_case` is the only code that reads a VulnCase for a query and
reads exactly `summary` and `details` from it (tested with an access-recording mapping).
"""

from dataclasses import dataclass
from typing import Any, Mapping

QUERY_FIELDS = ("summary", "details")


@dataclass(frozen=True)
class QueryInput:
    summary: str
    details: str


def query_input_from_case(case: Mapping[str, Any]) -> QueryInput:
    return QueryInput(summary=str(case["summary"] or ""), details=str(case.get("details") or ""))


def build_query(q: QueryInput) -> str:
    if not isinstance(q, QueryInput):
        raise TypeError("build_query takes a QueryInput (summary and details only), not a case")
    return "\n\n".join(part for part in (q.summary.strip(), q.details.strip()) if part)
