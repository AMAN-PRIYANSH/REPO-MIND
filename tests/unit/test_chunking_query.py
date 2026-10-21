"""Chunk construction (three variants, caps, masking) and the query leakage guarantee (CP4 D1)."""

import pytest

from vulntrace.retrieval import chunking
from vulntrace.retrieval.chunking import (
    CHUNK_CHAR_CAP,
    COMMIT_CHAR_CAP,
    ID_PLACEHOLDER,
    VARIANT_CODE_COMMITS,
    VARIANT_CODE_COMMITS_MASKED,
    VARIANT_CODE_ONLY,
    build_chunks,
    chunk_stats,
    import_path,
    mask_advisory_ids,
)
from vulntrace.retrieval.query import QueryInput, build_query, query_input_from_case

RK = "github.com/o/r@1.0.0..1.0.1"


def _rr(commits=None, body_b="func B() {}"):
    return {
        "case_id": "GO-2026-0001", "module": "github.com/o/r",
        "from": {"version": "1.0.0", "ref": "v1.0.0", "commit": "a" * 40},
        "to": {"version": "1.0.1", "ref": "v1.0.1", "commit": "b" * 40},
        "candidates": [
            {"candidate_id": "r1", "package_dir": "pkg/x", "symbol": "Server.Handle", "side": "BOTH",
             "old_range": {"file": "pkg/x/s.go", "start": 3, "end": 5},
             "new_range": {"file": "pkg/x/s.go", "start": 3, "end": 6}},
            {"candidate_id": "r2", "package_dir": "", "symbol": "B", "side": "NEW", "old_range": None,
             "new_range": {"file": "b.go", "start": 1, "end": 1}},
        ],
        "commits": commits if commits is not None else [
            {"sha": "c2", "subject": "fix CVE-2026-1111 in handler", "body": "", "touches_candidates": ["r1"]},
            {"sha": "c1", "subject": "add B", "body": "", "touches_candidates": ["r2"]},
            {"sha": "c0", "subject": "fix CVE-2026-1111 in handler", "body": "", "touches_candidates": ["r1"]},
        ],
    }


def _code(body_b="func B() {}"):
    return {"candidates": {
        "r1": {"package_name": "x", "doc": "// Handle serves GHSA-abcd-efgh-ijkl requests.",
               "signature": "func (s *Server) Handle(r *Request)", "body": "func (s *Server) Handle(r *Request) {\n}",
               "body_side": "OLD", "file": "pkg/x/s.go"},
        "r2": {"package_name": "r", "doc": "", "signature": "func B()", "body": body_b, "body_side": "NEW",
               "file": "b.go"},
    }}


def test_chunk_fields_and_stable_ids():
    chunks = build_chunks(RK, _rr(), _code(), "o", "r")
    c1, c2 = chunks
    assert c1.chunk_id == f"{RK}|r1|pkg/x/s.go|Server.Handle"
    assert c1.package == "github.com/o/r/pkg/x" and c2.package == "github.com/o/r"
    assert c1.version == "1.0.0" and c1.body_side == "OLD" and c2.body_side == "NEW" and c2.side == "NEW"
    assert c1.commit_subjects == ["fix CVE-2026-1111 in handler"]  # file-level, de-duplicated
    assert c2.commit_subjects == ["add B"]
    assert [c.chunk_id for c in build_chunks(RK, _rr(), _code(), "o", "r")] == [c1.chunk_id, c2.chunk_id]


def test_three_variants():
    c1 = build_chunks(RK, _rr(), _code(), "o", "r")[0]
    only = c1.text(VARIANT_CODE_ONLY).text
    with_commits = c1.text(VARIANT_CODE_COMMITS).text
    masked = c1.text(VARIANT_CODE_COMMITS_MASKED).text
    assert "commits:" not in only and "func (s *Server) Handle" in only and "package github.com/o/r/pkg/x" in only
    assert "commits: fix CVE-2026-1111 in handler" in with_commits
    assert "CVE-2026-1111" not in masked and "GHSA-abcd-efgh-ijkl" not in masked
    assert f"commits: fix {ID_PLACEHOLDER} in handler" in masked
    assert f"serves {ID_PLACEHOLDER} requests" in masked  # ids in code comments are masked too
    assert "GHSA-abcd-efgh-ijkl" in only  # code_only is unmasked: the doc comment is code
    hashes = {c1.text(v).content_sha256 for v in chunking.VARIANTS}
    assert len(hashes) == 3
    with pytest.raises(ValueError):
        c1.text("nope")


def test_text_order_puts_metadata_and_commits_before_the_body():
    c1 = build_chunks(RK, _rr(), _code(), "o", "r")[0]
    t = c1.text(VARIANT_CODE_COMMITS).text
    assert t.index("package") < t.index("func Server.Handle") < t.index("commits:") < t.index("// Handle") \
        < t.index("func (s *Server)")


def test_caps_are_applied_and_counted():
    long_body = "func B() {\n" + "x := 1\n" * 1000 + "}"
    commits = [{"sha": f"c{i}", "subject": f"subject number {i} " + "y" * 30, "body": "",
                "touches_candidates": ["r2"]} for i in range(40)]
    chunks = build_chunks(RK, _rr(commits=commits), _code(body_b=long_body), "o", "r")
    t = chunks[1].text(VARIANT_CODE_COMMITS)
    assert len(t.text) == CHUNK_CHAR_CAP and t.truncated and t.commits_truncated
    commit_line = [ln for ln in t.text.splitlines() if ln.startswith("commits:")][0]
    assert len(commit_line) == COMMIT_CHAR_CAP
    stats = chunk_stats(chunks)
    assert stats["truncated[code_only]"] == 1 and stats["commits_truncated[code_only]"] == 0
    assert stats["commits_truncated[code+commits]"] == 1
    assert stats["id_in_code"] == 1 and stats["id_in_commit_subjects"] == 0  # these commits carry no id
    assert stats["body_side_new"] == 1
    assert chunk_stats(build_chunks(RK, _rr(), _code(), "o", "r"))["id_in_commit_subjects"] == 1


def test_masking_happens_before_truncation_so_no_partial_id_survives():
    subject = "z" * (COMMIT_CHAR_CAP - len("commits: ") - 6) + " CVE-2026-123456"
    commits = [{"sha": "c", "subject": subject, "body": "", "touches_candidates": ["r1"]}]
    c1 = build_chunks(RK, _rr(commits=commits), _code(), "o", "r")[0]
    masked = c1.text(VARIANT_CODE_COMMITS_MASKED).text
    assert "CVE-2026" not in masked and "CVE" not in masked


def test_mask_advisory_ids_patterns():
    assert mask_advisory_ids("see cve-2021-44228 and GHSA-jfh8-c2jp-5v3q, GO-2022-0001.") == \
        f"see {ID_PLACEHOLDER} and {ID_PLACEHOLDER}, {ID_PLACEHOLDER}."
    assert mask_advisory_ids("CVE-21-1 GO-2022 GHSA-abc") == "CVE-21-1 GO-2022 GHSA-abc"


def test_import_path_handles_submodules_and_major_versions():
    assert import_path("github.com/o/r/v4", "pkg/a", "o", "r") == "github.com/o/r/v4/pkg/a"
    assert import_path("github.com/o/r/sdk", "sdk/client", "o", "r") == "github.com/o/r/sdk/client"
    assert import_path("github.com/o/r/sdk", "sdk", "o", "r") == "github.com/o/r/sdk"
    assert import_path("example.com/vanity", "", "o", "r") == "example.com/vanity"


class RecordingCase(dict):
    """A VulnCase that records which keys were read."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.read = set()

    def __getitem__(self, k):
        self.read.add(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        self.read.add(k)
        return super().get(k, default)


def _case_with_gold_sentinels():
    return RecordingCase({
        "id": "GO-2026-0001", "aliases": ["CVE-2026-9999"], "summary": "Path traversal in local backend",
        "details": "An attacker can escape the root.",
        "fix_commits": [{"host": "github.com", "owner": "o", "repo": "r", "sha": "f1x" * 13 + "f"}],
        "fix_references": [{"url": "https://github.com/o/r/commit/SENTINELFIXREF", "kind": "GITHUB_COMMIT"}],
        "modules": [{"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
                     "packages": [{"package": "github.com/o/r/backend", "core_symbols": ["SentinelCoreSym"],
                                   "derived_symbols": ["SentinelDerivedSym"]}]}],
    })


def test_query_builder_reads_only_summary_and_details():
    case = _case_with_gold_sentinels()
    q = build_query(query_input_from_case(case))
    assert case.read == {"summary", "details"}
    assert q == "Path traversal in local backend\n\nAn attacker can escape the root."
    for sentinel in ("SentinelCoreSym", "SentinelDerivedSym", "SENTINELFIXREF", "f1x", "CVE-2026-9999",
                     "GO-2026-0001", "github.com/o/r/backend"):
        assert sentinel not in q


def test_query_builder_rejects_a_raw_case_and_input_has_only_two_fields():
    with pytest.raises(TypeError):
        build_query(_case_with_gold_sentinels())
    assert set(QueryInput.__dataclass_fields__) == {"summary", "details"}
    assert build_query(QueryInput("only a summary", "")) == "only a summary"


def test_query_names_symbol_is_whole_word_case_sensitive_bare_name():
    from vulntrace.eval.retrieval import query_names_symbol

    assert query_names_symbol("Fs.Move does not check paths", {"Fs.Move"})
    assert query_names_symbol("calling Move with ..", {"Fs.Move"})
    assert not query_names_symbol("files are moved", {"Fs.Move"})       # case-sensitive
    assert not query_names_symbol("Remover breaks", {"Fs.Move"})        # whole word only
    assert not query_names_symbol("anything", set())
