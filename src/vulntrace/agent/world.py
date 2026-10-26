"""What the agent's tools may see about one case: its closed pool (CP6 deliverable 1).

A `CaseWorld` holds exactly the case's candidates (the functions changed in its release range),
the commits of that range, optionally their Go diffs and the precomputed call-graph neighbours,
and a search function over the candidates. It is built from the materialised evidence and the
fixed retriever; it never holds the fix commit, the gold symbols or `derived_symbols`, so no
tool can answer with them. Anything outside the pool is an error observation, never data.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from vulntrace.retrieval.query import QueryInput


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    package: str
    symbol: str
    file: str
    start: int | None
    end: int | None
    side: str          # OLD, NEW or BOTH: where the function exists
    body_side: str     # which release the code comes from
    signature: str
    doc: str
    body: str
    commit_subjects: tuple[str, ...] = ()


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str
    touches: tuple[str, ...]   # candidate IDs in files the commit changed (file level, as in CP3)


@dataclass
class CaseWorld:
    case_id: str
    advisory: QueryInput
    candidates: dict[str, Candidate]                  # candidate order of the release range
    commits: list[Commit]                             # newest first, as `git log` lists them
    search: Callable[[str], list[str]]                # query -> every candidate ID, best first
    initial_ranking: list[str]                        # the fixed retriever on the advisory text (= arm A0)
    commit_diffs: Mapping[str, dict[str, Any]] | None = None   # sha -> {"diff": str, "error": str|None}
    commit_diffs_note: str | None = None              # why diffs are missing, if they are
    graph: Mapping[str, dict[str, Any]] | None = None          # candidate id -> {"status", "callers", "callees"}
    graph_note: str | None = None                     # why the neighbour table is missing, if it is
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def pool(self) -> frozenset[str]:
        return frozenset(self.candidates)

    def commit_shas(self) -> list[str]:
        return [c.sha for c in self.commits]


def candidates_from_chunks(chunks, rr: Mapping[str, Any]) -> dict[str, Candidate]:
    """From the CP4 chunks of a range plus its ReleaseRange (for line numbers)."""
    ranges = {c["candidate_id"]: c for c in rr["candidates"]}
    out = {}
    for ch in chunks:
        rc = ranges.get(ch.candidate_id, {})
        rng = (rc.get("old_range") if ch.body_side == "OLD" else rc.get("new_range")) or rc.get("old_range") \
            or rc.get("new_range") or {}
        out[ch.candidate_id] = Candidate(ch.candidate_id, ch.package, ch.symbol, ch.file, rng.get("start"), rng.get("end"),
                                         ch.side, ch.body_side, ch.signature, ch.doc, ch.body, tuple(ch.commit_subjects))
    return out


def commits_from_range(rr: Mapping[str, Any]) -> list[Commit]:
    return [Commit(c["sha"], c.get("subject", ""), c.get("body", ""), tuple(c.get("touches_candidates", ())))
            for c in rr["commits"]]
