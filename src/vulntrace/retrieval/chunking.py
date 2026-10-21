"""Function-level chunks for Mode 2 retrieval (CP4 deliverable 1).

One chunk per candidate function of one release range; the corpus searched for a case is its
own range's candidates, never the whole repository. Cases with an identical range (same
`range_key`) share one set of chunks.

Chunk text, in this order so that a model's length limit cuts the function body last:

    package <import path>
    func <symbol>
    commits: <subject>; <subject>; ...        (only in the variants with commits)
    <doc comment>
    <declaration and body>

Variants (leakage controls):
- `code_only`: no commit text.
- `code+commits`: subjects of the range's commits that touched the candidate's file
  (file-level, as in CP3; newest first, de-duplicated).
- `code+commits_idmasked`: as `code+commits`, with every advisory identifier (CVE, GHSA, GO
  ids) anywhere in the text replaced by `ADVISORYID`.

Caps: the commit line is cut at `COMMIT_CHAR_CAP` characters and the whole text at
`CHUNK_CHAR_CAP` characters (about 512 model tokens, so lexical and dense retrieval see
roughly the same text). Every cut is counted.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from vulntrace.dataset.release_range import module_subdir

VARIANT_CODE_ONLY = "code_only"
VARIANT_CODE_COMMITS = "code+commits"
VARIANT_CODE_COMMITS_MASKED = "code+commits_idmasked"
VARIANTS = (VARIANT_CODE_ONLY, VARIANT_CODE_COMMITS, VARIANT_CODE_COMMITS_MASKED)

CHUNK_CHAR_CAP = 2000
COMMIT_CHAR_CAP = 500
ID_PLACEHOLDER = "ADVISORYID"

# CVE-2026-12345, GHSA-xxxx-xxxx-xxxx (4-character groups of [23456789cfghjmpqrvwx]; matched
# loosely as alphanumerics), GO-2026-1234. Case-insensitive.
ADVISORY_ID_RE = re.compile(r"\b(?:CVE-\d{4}-\d{4,}|GHSA(?:-[0-9a-z]{4}){3}|GO-\d{4}-\d{4,})\b", re.IGNORECASE)


def mask_advisory_ids(text: str) -> str:
    return ADVISORY_ID_RE.sub(ID_PLACEHOLDER, text)


def has_advisory_id(text: str) -> bool:
    return ADVISORY_ID_RE.search(text) is not None


def import_path(module: str, package_dir: str, fix_owner: str, fix_repo: str) -> str:
    """Best-effort Go import path of a candidate's package: the module path plus the package
    directory relative to the module's subdirectory in the repository (CP3's
    `module_subdir`); directories outside it are appended as they are (documented
    approximation for multi-module repositories)."""
    sub = module_subdir(module, fix_owner, fix_repo)
    rel = package_dir
    if sub and (package_dir == sub or package_dir.startswith(sub + "/")):
        rel = package_dir[len(sub):].lstrip("/")
    return module + ("/" + rel if rel else "")


@dataclass
class Chunk:
    chunk_id: str
    range_key: str
    candidate_id: str
    module: str
    version: str
    package: str
    package_name: str
    symbol: str
    file: str
    side: str
    body_side: str
    signature: str
    doc: str
    body: str
    commit_subjects: list[str] = field(default_factory=list)

    def text(self, variant: str) -> "ChunkText":
        if variant not in VARIANTS:
            raise ValueError(f"unknown chunk variant {variant!r}")
        # Masking happens before any cap, so a cut can never leave a partial id behind.
        mask = mask_advisory_ids if variant == VARIANT_CODE_COMMITS_MASKED else (lambda t: t)
        head = [f"package {self.package}", f"func {self.symbol}"]
        commits_truncated = False
        if variant != VARIANT_CODE_ONLY and self.commit_subjects:
            line = mask("commits: " + "; ".join(self.commit_subjects))
            if len(line) > COMMIT_CHAR_CAP:
                line, commits_truncated = line[:COMMIT_CHAR_CAP], True
            head.append(line)
        if self.doc:
            head.append(mask(self.doc))
        text = "\n".join(head) + "\n" + mask(self.body)
        truncated = len(text) > CHUNK_CHAR_CAP
        text = text[:CHUNK_CHAR_CAP]
        return ChunkText(self.chunk_id, variant, text, hashlib.sha256(text.encode("utf-8")).hexdigest(),
                         truncated, commits_truncated)

    def metadata(self, variant: str, embedding_model: str, content_sha256: str) -> dict[str, str]:
        return {"variant": variant, "embedding_model": embedding_model, "range_key": self.range_key,
                "module": self.module, "version": self.version, "package": self.package, "symbol": self.symbol,
                "candidate_id": self.candidate_id, "content_sha256": content_sha256}


@dataclass
class ChunkText:
    chunk_id: str
    variant: str
    text: str
    content_sha256: str
    truncated: bool
    commits_truncated: bool


def commit_subjects_by_candidate(rr: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for commit in rr["commits"]:  # newest first, as `git log` lists them
        subject = commit["subject"].strip()
        if not subject:
            continue
        for cid in commit["touches_candidates"]:
            lst = out.setdefault(cid, [])
            if subject not in lst:
                lst.append(subject)
    return out


def build_chunks(range_key: str, rr: dict[str, Any], code: dict[str, Any], fix_owner: str,
                 fix_repo: str) -> list[Chunk]:
    """Chunks for one release range, in candidate order. `rr` is the ReleaseRange, `code`
    its `data/candidate_code` companion. `version` is the vulnerable version (bodies come
    from it, except for functions that exist only in the fixed version)."""
    subjects = commit_subjects_by_candidate(rr)
    chunks = []
    for cand in rr["candidates"]:
        cid = cand["candidate_id"]
        c = code["candidates"].get(cid) or {}
        rng = cand["old_range"] or cand["new_range"]
        chunks.append(Chunk(
            chunk_id=f"{range_key}|{cid}|{rng['file']}|{cand['symbol']}", range_key=range_key, candidate_id=cid,
            module=rr["module"], version=rr["from"]["version"],
            package=import_path(rr["module"], cand["package_dir"], fix_owner, fix_repo),
            package_name=c.get("package_name", ""), symbol=cand["symbol"], file=rng["file"], side=cand["side"],
            body_side=c.get("body_side", "OLD" if cand["side"] != "NEW" else "NEW"),
            signature=c.get("signature", ""), doc=c.get("doc", ""), body=c.get("body", ""),
            commit_subjects=subjects.get(cid, []),
        ))
    return chunks


def chunk_stats(chunks: list[Chunk]) -> dict[str, Any]:
    """Counts the results document reports: truncation per variant and where advisory ids occur."""
    out: dict[str, Any] = {"chunks": len(chunks), "missing_body": sum(1 for c in chunks if not c.body),
                           "body_side_new": sum(1 for c in chunks if c.body_side == "NEW"),
                           "with_commit_subjects": sum(1 for c in chunks if c.commit_subjects),
                           "id_in_code": sum(1 for c in chunks if has_advisory_id(c.doc + "\n" + c.body)),
                           "id_in_commit_subjects": sum(1 for c in chunks if has_advisory_id("\n".join(c.commit_subjects)))}
    for v in VARIANTS:
        texts = [c.text(v) for c in chunks]
        out[f"truncated[{v}]"] = sum(1 for t in texts if t.truncated)
        out[f"commits_truncated[{v}]"] = sum(1 for t in texts if t.commits_truncated)
    return out
