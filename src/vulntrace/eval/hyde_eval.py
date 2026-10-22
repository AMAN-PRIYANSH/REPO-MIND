"""HyDE evaluation on D4 (CP5 deliverable 5, question 3): does a hypothetical function written by
the LLM improve retrieval?

For every case the model writes one hypothetical function from the advisory text (cached, so a
re-run costs nothing). Each retriever is then run with three queries: the original query
(= CP4), `query+hyde` and `hyde-only`, on the same cases and chunks. Runs are written in the CP4
run format (so the CP4 metrics and paired cluster bootstrap apply unchanged) with an extra
`hyde` key. The hypothetical text itself is never written to a result file.
"""

from typing import Any, Callable

from vulntrace.eval import retrieval as er
from vulntrace.llm import hyde
from vulntrace.models.llm import LLMClient
from vulntrace.retrieval.query import QueryInput

SCHEMA_VERSION = "1.0"


def generate_all(client: LLMClient, cases: list[er.EvalCase],
                 progress: Callable[[int, int, str], None] | None = None) -> dict[str, hyde.HydeResult]:
    out: dict[str, hyde.HydeResult] = {}
    errors = 0
    for i, case in enumerate(cases, start=1):
        r = hyde.generate(client, QueryInput(case.summary, case.details))
        out[case.case_id] = r
        errors = errors + 1 if r.error else 0
        if errors >= 3:
            raise RuntimeError(f"3 HyDE generations in a row failed ({r.error}); is the LLM server up? Nothing is written.")
        if progress:
            progress(i, len(cases), f"{case.case_id} {'empty' if r.empty else str(len(r.text)) + ' chars'}")
    return out


def run_hyde(harness: er.Harness, configs: list[er.Config], chunk_variant: str, variants: list[str],
             hypotheticals: dict[str, hyde.HydeResult]) -> list[dict[str, Any]]:
    """One CP4-format run per (config, HyDE variant). `query` is always included."""
    variants = list(dict.fromkeys([hyde.VARIANT_QUERY, *variants]))
    runs = []
    try:
        for cfg in configs:
            for v in variants:
                queries = {c.case_id: hyde.assemble_query(v, c.query, hypotheticals[c.case_id].text)
                           for c in harness._base_cases}
                harness.set_queries(queries)
                run = harness.run(cfg, chunk_variant)
                run["hyde"] = v
                run["hyde_prompt"] = hyde.prompt_version()
                runs.append(run)
    finally:
        harness.set_queries(None)
    return runs


def hyde_meta(client: LLMClient, cases: list[er.EvalCase], hypotheticals: dict[str, hyde.HydeResult]) -> dict[str, Any]:
    rows = [{"id": c.case_id, "created": c.created, **hypotheticals[c.case_id].row()} for c in cases]
    return {"schema_version": SCHEMA_VERSION, "prompt": hyde.prompt_version(), "char_cap": hyde.HYDE_CHAR_CAP,
            "settings": hyde.HYDE_SETTINGS.as_dict(), "model": client.info(),
            "counts": {"cases": len(rows), "empty": sum(r["empty"] for r in rows),
                       "truncated": sum(r["truncated"] for r in rows), "errors": sum(1 for r in rows if r["error"]),
                       "input_tokens": sum(r["input_tokens"] or 0 for r in rows),
                       "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
                       "llm_seconds": round(sum(r["latency_s"] or 0 for r in rows), 1)},
            "rows": rows}
