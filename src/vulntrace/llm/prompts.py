"""Prompt templates (versioned text files in `prompts/`) and the two prompt builders (CP5 deliverable 3).

What each builder can see is fixed by its input type, not by discipline:

- Mode 1 (`FixPromptInput`): advisory summary and details, the changed functions of the fix
  commit (id, symbol, file, side, hunk ids) and its numbered non-test hunks. There is no field
  for the curated core symbols or `derived_symbols`; the case is read only through
  `query_input_from_case`, which reads `summary` and `details`. (The candidates *are* the
  functions the fix changed, so the gold functions appear among them by construction; what the
  prompt never contains is the gold *label*.)
- Mode 2 (`TopkPromptInput`): advisory summary and details and the top-k candidates (id, package,
  symbol, signature, commit subjects of the range that touched the candidate's file, doc
  comment, body). No fix commit, no gold, no `derived_symbols`.

Untrusted text is wrapped in `<<<BEGIN name>>>` / `<<<END name>>>` markers and described to the
model as data; the markers themselves are neutralised inside untrusted text so it cannot close
its own block. Truncation rules are constants stated here and every cut is counted in the
prompt's `meta`.
"""

import hashlib
from dataclasses import dataclass, field
from importlib import resources
from string import Template
from typing import Any, Mapping

from vulntrace.retrieval.query import QueryInput

MODE_FIX, MODE_RELEASE = "fix", "release"
MAX_SELECTED = {MODE_FIX: 5, MODE_RELEASE: 3}

# Truncation rules (stated, recorded per case)
ADVISORY_DETAILS_CHAR_CAP = 4000       # advisory details
HUNK_CHAR_CAP = 2500                   # one hunk of the fix diff
DIFF_CHAR_BUDGET = 20000               # all hunks together; later hunks are omitted once it is used up
CANDIDATE_BODY_CHAR_CAP = 1500         # doc comment + body of one Mode 2 candidate
CANDIDATE_COMMITS_CHAR_CAP = 500       # commit subjects of one Mode 2 candidate
SINGLE_LINE_CAP = 200                  # package paths, file names, signatures

FIX_PROMPT = "root_cause_fix_v1"
TOPK_PROMPT = "root_cause_topk_v1"
SYSTEM_PROMPT = "root_cause_system_v1"
RETRY_PROMPT = "root_cause_retry_v1"
HYDE_PROMPT = "hyde_v1"
HYDE_SYSTEM_PROMPT = "hyde_system_v1"


def template_text(name: str) -> str:
    return resources.files("vulntrace.llm").joinpath("prompts", f"{name}.txt").read_text(encoding="utf-8")


def template_sha256(*names: str) -> str:
    h = hashlib.sha256()
    for n in names:
        h.update(n.encode("utf-8") + b"\0" + template_text(n).encode("utf-8") + b"\0")
    return h.hexdigest()


def escape_untrusted(text: str) -> tuple[str, int]:
    """Neutralise the block markers inside untrusted text. Returns (text, number of escapes)."""
    n = text.count("<<<") + text.count(">>>")
    return text.replace("<<<", "<< <").replace(">>>", ">> >"), n


def one_line(text: str, cap: int = SINGLE_LINE_CAP) -> str:
    return " ".join(str(text).split())[:cap]


def cut(text: str, cap: int) -> tuple[str, bool]:
    return (text[:cap], True) if len(text) > cap else (text, False)


@dataclass(frozen=True)
class Prompt:
    version: str            # e.g. "root_cause_fix_v1"
    sha256: str             # of the template files used
    system: str
    user: str
    candidate_ids: tuple[str, ...]
    max_selected: int
    meta: dict[str, Any] = field(default_factory=dict)

    def messages(self) -> list[dict[str, str]]:
        return [{"role": "system", "content": self.system}, {"role": "user", "content": self.user}]


def _advisory(a: QueryInput, meta: dict[str, Any]) -> tuple[str, str]:
    summary, n1 = escape_untrusted(one_line(a.summary, 500))
    details, cut_flag = cut(a.details.strip(), ADVISORY_DETAILS_CHAR_CAP)
    details, n2 = escape_untrusted(details)
    meta["advisory_details_truncated"] = cut_flag
    meta["delimiter_escapes"] = meta.get("delimiter_escapes", 0) + n1 + n2
    return summary, details or "(none)"


# --- Mode 1 ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class FixCandidate:
    candidate_id: str
    symbol: str
    file: str
    side: str
    hunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class FixHunk:
    hunk_id: str
    file: str
    text: str


@dataclass(frozen=True)
class FixPromptInput:
    advisory: QueryInput
    candidates: tuple[FixCandidate, ...]
    hunks: tuple[FixHunk, ...]


def fix_input(advisory: QueryInput, evidence: Mapping[str, Any]) -> FixPromptInput:
    """From a FixEvidence document. Reads candidates (id, symbol, ranges, hunk ids) and hunks only."""
    cands = []
    for c in evidence["candidates"]:
        rng = c.get("new_range") or c.get("old_range") or {}
        cands.append(FixCandidate(c["candidate_id"], c["symbol"], rng.get("file", ""), c["side"], tuple(c["hunk_ids"])))
    hunks = tuple(FixHunk(h["hunk_id"], h["file"], h["text"]) for h in evidence["hunks"])
    return FixPromptInput(advisory, tuple(cands), hunks)


def build_fix_prompt(inp: FixPromptInput) -> Prompt:
    meta: dict[str, Any] = {}
    summary, details = _advisory(inp.advisory, meta)
    cand_blocks = []
    for c in inp.candidates:
        hunks = ", ".join(c.hunk_ids) if c.hunk_ids else "none"
        cand_blocks.append(f"ID: {c.candidate_id}\nFunction: {one_line(c.symbol)}\nFile: {one_line(c.file)}\n"
                           f"Changed on the {c.side} side, in hunks: {hunks}")
    # diff: whole hunks in order; each capped; stop when the budget is used
    shown, used, cut_hunks, omitted, escapes = [], 0, 0, [], 0
    for h in inp.hunks:
        text, was_cut = cut(h.text, HUNK_CHAR_CAP)
        text, n = escape_untrusted(text)
        block = f"[{h.hunk_id}] {one_line(h.file)}\n{text}" + ("\n[hunk truncated]" if was_cut else "")
        if used + len(block) > DIFF_CHAR_BUDGET and shown:
            omitted.append(h.hunk_id)
            continue
        shown.append(block)
        used += len(block)
        cut_hunks += was_cut
        escapes += n
    note = (f"{len(omitted)} further hunk(s) are not shown because of the size limit ({', '.join(omitted[:20])}"
            f"{', ...' if len(omitted) > 20 else ''}); candidates touched only by them are still selectable."
            if omitted else "")
    meta.update({"hunks_total": len(inp.hunks), "hunks_shown": len(shown), "hunks_omitted": len(omitted),
                 "hunks_truncated": cut_hunks, "diff_truncated": bool(omitted or cut_hunks), "diff_chars": used,
                 "candidates": len(inp.candidates)})
    meta["delimiter_escapes"] += escapes
    n_max = MAX_SELECTED[MODE_FIX]
    user = Template(template_text(FIX_PROMPT)).substitute(
        summary=summary, details=details, candidates="\n\n".join(cand_blocks) or "(none)",
        diff="\n\n".join(shown) or "(no hunks)", diff_note=note, max_selected=n_max)
    return Prompt(FIX_PROMPT, template_sha256(SYSTEM_PROMPT, FIX_PROMPT, RETRY_PROMPT), template_text(SYSTEM_PROMPT).strip(),
                  user, tuple(c.candidate_id for c in inp.candidates), n_max, meta)


# --- Mode 2 ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class TopkCandidate:
    candidate_id: str
    package: str
    symbol: str
    signature: str
    commit_subjects: tuple[str, ...]
    doc: str
    body: str


@dataclass(frozen=True)
class TopkPromptInput:
    advisory: QueryInput
    candidates: tuple[TopkCandidate, ...]   # in retrieval order


def topk_candidate(chunk) -> TopkCandidate:
    """From a retrieval `Chunk`: copies exactly the seven candidate-side fields below."""
    return TopkCandidate(chunk.candidate_id, chunk.package, chunk.symbol, chunk.signature,
                         tuple(chunk.commit_subjects), chunk.doc, chunk.body)


def build_topk_prompt(inp: TopkPromptInput) -> Prompt:
    meta: dict[str, Any] = {}
    summary, details = _advisory(inp.advisory, meta)
    blocks, cut_bodies, cut_commits, escapes = [], 0, 0, 0
    for c in inp.candidates:
        code, was_cut = cut((c.doc.strip() + "\n" + c.body).strip(), CANDIDATE_BODY_CHAR_CAP)
        code, n1 = escape_untrusted(code)
        commits, commits_cut = cut("; ".join(c.commit_subjects), CANDIDATE_COMMITS_CHAR_CAP)
        commits, n2 = escape_untrusted(commits)
        cut_bodies += was_cut
        cut_commits += commits_cut
        escapes += n1 + n2
        head = (f"ID: {c.candidate_id}\nFunction: {one_line(c.package)}.{one_line(c.symbol)}\n"
                f"Signature: {one_line(c.signature) or '(unknown)'}")
        parts = [head]
        if commits:
            parts.append(f"<<<BEGIN COMMITS {c.candidate_id}>>>\n{commits}\n<<<END COMMITS {c.candidate_id}>>>")
        parts.append(f"<<<BEGIN CODE {c.candidate_id}>>>\n{code or '(no source available)'}"
                     f"{chr(10) + '[code truncated]' if was_cut else ''}\n<<<END CODE {c.candidate_id}>>>")
        blocks.append("\n".join(parts))
    meta.update({"candidates": len(inp.candidates), "bodies_truncated": cut_bodies, "commit_lines_truncated": cut_commits})
    meta["delimiter_escapes"] += escapes
    n_max = MAX_SELECTED[MODE_RELEASE]
    user = Template(template_text(TOPK_PROMPT)).substitute(
        summary=summary, details=details, candidates="\n\n".join(blocks) or "(none)", max_selected=n_max)
    return Prompt(TOPK_PROMPT, template_sha256(SYSTEM_PROMPT, TOPK_PROMPT, RETRY_PROMPT), template_text(SYSTEM_PROMPT).strip(),
                  user, tuple(c.candidate_id for c in inp.candidates), n_max, meta)


def retry_message(problems_text: str, candidate_ids: tuple[str, ...], max_selected: int) -> str:
    ids = ", ".join(candidate_ids[:200]) + (", ..." if len(candidate_ids) > 200 else "")
    return Template(template_text(RETRY_PROMPT)).substitute(problems=problems_text, ids=ids or "(none)",
                                                           max_selected=max_selected).strip()
