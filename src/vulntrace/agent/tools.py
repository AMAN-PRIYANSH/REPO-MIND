"""The agent's tools (contract: INTERFACES_AND_CONTRACTS.md section 5, "Agent tools").

Every tool reads only the case's `CaseWorld` (closed pool). An ID or SHA outside the case gives an
error observation that names no data. Output is capped at `Budget.max_tool_chars` characters:
list outputs drop whole entries from the end, single-item outputs cut their code or diff text,
and either way the output says what was cut. Third-party text is escaped so it cannot close the
`<<<BEGIN TOOL OUTPUT>>>` block it is shown in.

Each call returns an `Observation`: the text for the model, a short code-free summary for the
committed trace rows, and which candidate IDs and commit SHAs the model has now seen (the
evidence `submit_answer` may cite).
"""

from dataclasses import dataclass, field

from vulntrace.agent import protocol as P
from vulntrace.agent.world import CaseWorld, Candidate
from vulntrace.llm.prompts import escape_untrusted, one_line
from vulntrace.retrieval.bm25 import BM25
from vulntrace.retrieval.tokenize import code_tokens

SHORT_SHA = 12
QUERY_CHAR_CAP = 500           # a longer query is cut (recorded), not rejected
COMMIT_RESULTS = 10
COMMIT_BODY_CAP = 800
TOUCHED_LIST_CAP = 20
NEIGHBOUR_LIST_CAP = 40
CANDIDATE_COMMITS_CAP = 5


@dataclass
class Observation:
    output: str
    summary: str
    ok: bool = True
    candidates_shown: tuple[str, ...] = ()
    commits_shown: tuple[str, ...] = ()
    truncated: bool = False
    full_chars: int = 0          # length before the cap
    notes: dict = field(default_factory=dict)


class ToolError(Exception):
    """A tool could not answer for a reason the model may be told (unknown ID, ...)."""


def _cap_entries(header: str, entries: list[tuple[str, tuple[str, ...]]], cap: int,
                 what: str) -> tuple[str, tuple[str, ...], bool, int]:
    """Header plus as many whole entries as fit in `cap` characters; the IDs of the entries shown."""
    full = "\n".join([header] + [e for e, _ in entries])
    if len(full) <= cap:
        return full, tuple(i for _, ids in entries for i in ids), False, len(full)
    lines, shown, used = [header], [], len(header)
    for i, (text, ids) in enumerate(entries):
        note = f"[{len(entries) - i} more {what} not shown: output limit of {cap} characters]"
        if used + 1 + len(text) + 1 + len(note) > cap:
            lines.append(note)
            break
        lines.append(text)
        used += 1 + len(text)
        shown.extend(ids)
    return "\n".join(lines), tuple(shown), True, len(full)


def _cap_text(head: str, body: str, cap: int) -> tuple[str, bool, int]:
    full = head + body
    if len(full) <= cap:
        return full, False, len(full)
    note = f"\n[cut: {len(full)} characters, the first {{keep}} shown]"
    keep = max(0, cap - len(note))              # filling in {keep} (at most 5 digits) only shortens the note
    return full[:keep] + note.replace("{keep}", str(keep)), True, len(full)


def candidate_line(rank: int | None, c: Candidate) -> str:
    sig = one_line(c.signature, 140) or f"func {one_line(c.symbol, 100)}"
    head = f"{rank}. " if rank is not None else ""
    line = f"{head}[{c.candidate_id}] {one_line(c.package, 90)}.{one_line(c.symbol, 80)} | {sig}"
    if c.commit_subjects:
        line += f"\n   commit: {one_line(c.commit_subjects[0], 100)}"
    return line


def search_listing(world: CaseWorld, ranking: list[str], k: int, cap: int, header: str) -> tuple[str, tuple[str, ...], bool, int]:
    entries = [(candidate_line(i, world.candidates[cid]), (cid,)) for i, cid in enumerate(ranking[:k], start=1)
               if cid in world.candidates]
    return _cap_entries(header, entries, cap, "results")


class Tools:
    def __init__(self, world: CaseWorld, max_chars: int, graph_tools: bool):
        self.world, self.max_chars = world, max_chars
        self.graph_tools = bool(graph_tools and world.graph is not None)
        self._commit_bm25: BM25 | None = None
        self._touching: dict[str, list[str]] | None = None

    @property
    def names(self) -> tuple[str, ...]:
        if self.graph_tools:
            return P.BASE_TOOLS[:-1] + P.GRAPH_TOOLS + (P.SUBMIT,)
        return P.BASE_TOOLS

    # --- dispatch ---------------------------------------------------------------------------
    def run(self, action: P.Action) -> Observation:
        handler = {P.SEARCH_CODE: self.search_code, P.READ_FUNCTION: self.read_function,
                   P.SEARCH_COMMITS: self.search_commits, P.SHOW_COMMIT: self.show_commit,
                   P.CALLERS: self.callers, P.CALLEES: self.callees}.get(action.tool)
        if handler is None or (action.tool in P.GRAPH_TOOLS and not self.graph_tools):
            return self._error(f"{action.tool} is not a tool of this run", "UNKNOWN_TOOL")
        try:
            obs = handler(**action.args)
        except ToolError as exc:
            return self._error(str(exc), "TOOL_REFUSED")
        except Exception as exc:  # a broken tool must not end the run; the model is told it failed
            return self._error(f"the tool failed ({type(exc).__name__})", "TOOL_FAILED")
        text, n = escape_untrusted(obs.output)
        obs.output = text
        obs.notes["delimiter_escapes"] = n
        return obs

    def _error(self, message: str, code: str) -> Observation:
        return Observation(output=f"error: {message}", summary=f"error {code}", ok=False, notes={"error": code})

    def _candidate(self, cid: str) -> Candidate:
        c = self.world.candidates.get(cid)
        if c is None:
            raise ToolError(f"{one_line(cid, 40)!r} is not a candidate of this case; only IDs from the candidate pool "
                            "are accepted")
        return c

    # --- tools ------------------------------------------------------------------------------
    def search_code(self, query: str, k: int = P.SEARCH_K_DEFAULT) -> Observation:
        cut = len(query) > QUERY_CHAR_CAP
        ranking = self.world.search(query[:QUERY_CHAR_CAP])
        header = f"{min(k, len(ranking))} best of {len(self.world.candidates)} candidates for the query, best first:"
        text, shown, trunc, full = search_listing(self.world, ranking, k, self.max_chars, header)
        return Observation(text, f"{len(shown)} candidates", True, shown, (), trunc, full, {"query_cut": cut})

    def read_function(self, candidate_id: str) -> Observation:
        c = self._candidate(candidate_id)
        where = f"lines {c.start}-{c.end}" if c.start is not None else "lines unknown"
        version = "the fixed release (the function is new there)" if c.body_side == "NEW" else "the vulnerable release"
        commits = [s for s in self._touching_commits().get(c.candidate_id, [])][:CANDIDATE_COMMITS_CAP]
        sha_of = {x.sha: x for x in self.world.commits}
        head = [f"ID: {c.candidate_id}", f"Function: {one_line(c.package, 120)}.{one_line(c.symbol, 100)}",
                f"File: {one_line(c.file, 150)} {where}; code from {version}"]
        if commits:
            head.append("Commits of the range that changed this file: "
                        + "; ".join(f"{s[:SHORT_SHA]} {one_line(sha_of[s].subject, 80)}" for s in commits))
        code = (c.doc.strip() + "\n" + c.body).strip() or "(no source available)"
        text, trunc, full = _cap_text("\n".join(head) + "\n", code, self.max_chars)
        return Observation(text, f"{len(code.splitlines())} lines", True, (c.candidate_id,), tuple(commits), trunc, full)

    def search_commits(self, query: str) -> Observation:
        commits = self.world.commits
        if not commits:
            return Observation("The release range has no commits recorded.", "0 commits", True)
        if self._commit_bm25 is None:
            self._commit_bm25 = BM25([code_tokens(f"{c.subject}\n{c.body}") for c in commits])
        scores = self._commit_bm25.scores(code_tokens(query[:QUERY_CHAR_CAP]))
        order = sorted(range(len(commits)), key=lambda i: (-scores[i], i))[:COMMIT_RESULTS]
        matching = sum(1 for s in scores if s > 0)
        header = (f"{len(commits)} commits in the release range, {matching} share words with the query; "
                  f"{len(order)} best matches (ties in history order, newest first):")
        entries = [(f"{commits[i].sha[:SHORT_SHA]} {one_line(commits[i].subject, 140)} "
                    f"(touches {len(commits[i].touches)} candidates)", (commits[i].sha,)) for i in order]
        text, shown, trunc, full = _cap_entries(header, entries, self.max_chars, "commits")
        return Observation(text, f"{len(shown)} commits", True, (), shown, trunc, full)

    def show_commit(self, sha: str) -> Observation:
        ref = sha.strip().lower()
        if len(ref) < P.MIN_SHA_PREFIX:
            raise ToolError(f"give at least {P.MIN_SHA_PREFIX} characters of the SHA")
        hits = [c for c in self.world.commits if c.sha.lower().startswith(ref)]
        if not hits:
            raise ToolError(f"{one_line(sha, 40)!r} is not a commit of this release range")
        if len(hits) > 1:
            raise ToolError(f"{one_line(sha, 40)!r} matches {len(hits)} commits; give more characters")
        c = hits[0]
        touched = [t for t in c.touches if t in self.world.candidates]
        names = ", ".join(f"{t} ({one_line(self.world.candidates[t].symbol, 50)})" for t in touched[:TOUCHED_LIST_CAP])
        more = f", and {len(touched) - TOUCHED_LIST_CAP} more" if len(touched) > TOUCHED_LIST_CAP else ""
        body = c.body.strip()[:COMMIT_BODY_CAP] + (" [message cut]" if len(c.body.strip()) > COMMIT_BODY_CAP else "")
        head = (f"Commit {c.sha[:SHORT_SHA]}\nSubject: {one_line(c.subject, 200)}\nMessage: {body or '(none)'}\n"
                f"Touches {len(touched)} candidates: {names or 'none'}{more}\nDiff of Go files:\n")
        diffs = self.world.commit_diffs
        entry = diffs.get(c.sha) if diffs is not None else None
        if entry is None or entry.get("error"):
            why = (entry or {}).get("error") or self.world.commit_diffs_note or "not prepared for this case"
            diff = f"(the diff is not available: {one_line(why, 120)})"
            got = False
        else:
            diff, got = entry["diff"] or "(no Go files changed)", True
        text, trunc, full = _cap_text(head, diff, self.max_chars)
        return Observation(text, f"commit, {len(touched)} candidates, diff {'shown' if got else 'missing'}", True,
                           tuple(touched[:TOUCHED_LIST_CAP]), (c.sha,), trunc, full, {"diff_available": got})

    def callers(self, candidate_id: str) -> Observation:
        return self._neighbours(candidate_id, "callers")

    def callees(self, candidate_id: str) -> Observation:
        return self._neighbours(candidate_id, "callees")

    def _neighbours(self, candidate_id: str, direction: str) -> Observation:
        c = self._candidate(candidate_id)
        rec = (self.world.graph or {}).get(c.candidate_id)
        if rec is None or rec.get("status") not in ("FOUND", "NONE"):
            why = (rec or {}).get("status") or ("the function exists only in the fixed release" if c.side == "NEW"
                                                else "not in the call graph")
            return Observation(f"No call-graph information for {c.candidate_id}: {one_line(why, 120)}.",
                               "no graph info", True, (c.candidate_id,))
        edges = rec.get(direction) or []
        what = "Direct callers of" if direction == "callers" else "Functions called directly by"
        header = (f"{what} {c.candidate_id} ({one_line(c.symbol, 80)}) in the call graph of the vulnerable release: "
                  f"{len(edges) or 'none'}" + ("" if edges else " (calls from outside the module are not included)"))
        entries = []
        for e in edges[:NEIGHBOUR_LIST_CAP]:
            other = e.get("candidate_id")
            tag = f"[{other}]" if other in self.world.candidates else "[not a candidate]"
            site = f" at {one_line(e.get('file') or '?', 80)}:{e.get('line') or '?'}" if e.get("file") else ""
            entries.append((f"- {tag} {one_line(e['package'], 90)}.{one_line(e['symbol'], 80)}{site} ({e.get('kind', '?')})",
                            (other,) if other in self.world.candidates else ()))
        if len(edges) > NEIGHBOUR_LIST_CAP:
            entries.append((f"[{len(edges) - NEIGHBOUR_LIST_CAP} more not listed]", ()))
        text, shown, trunc, full = _cap_entries(header, entries, self.max_chars, "functions")
        return Observation(text, f"{len(edges)} {direction}", True, (c.candidate_id,) + shown, (), trunc, full)

    def _touching_commits(self) -> dict[str, list[str]]:
        if self._touching is None:
            out: dict[str, list[str]] = {}
            for c in self.world.commits:
                for t in c.touches:
                    out.setdefault(t, []).append(c.sha)
            self._touching = out
        return self._touching
