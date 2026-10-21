"""The whole retrieval harness end to end on a tiny synthetic D4, using only the fake models and
the in-memory store, with the network blocked and no model library importable (CP4 D8)."""

import json
import socket
import sys

import pytest

from vulntrace.__main__ import main
from vulntrace.eval import retrieval as er
from vulntrace.eval.retrieval_report import Summaries, load_results, render_cp4_doc
from vulntrace.retrieval.chunking import VARIANTS


@pytest.fixture(autouse=True)
def no_network_no_models(monkeypatch):
    def refuse(*a, **kw):
        raise AssertionError("the retrieval harness tried to open a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    for mod in ("sentence_transformers", "torch", "transformers"):
        monkeypatch.setitem(sys.modules, mod, None)  # importing any of them now raises ImportError


def _cand(cid, symbol, pkg, file, side="BOTH"):
    rng = {"file": file, "start": 1, "end": 3}
    return {"candidate_id": cid, "package_dir": pkg, "symbol": symbol, "side": side,
            "old_range": rng if side != "NEW" else None, "new_range": rng if side != "OLD" else None}


def _range(case_id, module, frm, to, cands, commits, status="AVAILABLE"):
    return {"schema_version": "1.0", "case_id": case_id, "module": module,
            "from": {"version": frm, "ref": f"v{frm}", "commit": "a" * 40},
            "to": {"version": to, "ref": f"v{to}", "commit": "b" * 40},
            "candidates": cands, "commits": commits, "non_go_files_changed": [], "test_files_changed": 0,
            "status": status}


BODIES = {
    "Local.Move": "func (f *Local) Move(src, dst string) error {\n\treturn os.Rename(cleanPath(src), dst)\n}",
    "Local.List": "func (f *Local) List(dir string) ([]string, error) {\n\treturn readDir(dir)\n}",
    "cleanPath": "func cleanPath(p string) string {\n\treturn filepath.Clean(p)\n}",
    "Config.Load": "func (c *Config) Load() error {\n\treturn yaml.Unmarshal(c.raw, c)\n}",
    "parseHeader": "func parseHeader(b []byte) (Header, error) {\n\treturn Header{}, nil\n}",
    "Server.Serve": "func (s *Server) Serve(l net.Listener) error {\n\treturn http.Serve(l, s)\n}",
}


def _vc(case_id, summary, details, module, frm, to, core, created, aliases=()):
    return {"id": case_id, "aliases": list(aliases), "summary": summary, "details": details, "created": created,
            "fix_commits": [{"host": "github.com", "owner": "o", "repo": "r", "sha": "f" * 40}],
            "modules": [{"module": module, "vulnerable_at": frm, "fixed_in": to,
                         "packages": [{"package": module, "core_symbols": core, "derived_symbols": ["Local.List"]}]}]}


@pytest.fixture
def tiny_d4(tmp_path):
    data = tmp_path / "data"
    r1 = [_cand("r1", "Local.Move", "backend/local", "backend/local/l.go"),
          _cand("r2", "Local.List", "backend/local", "backend/local/l.go"),
          _cand("r3", "cleanPath", "backend/local", "backend/local/p.go"),
          _cand("r4", "Config.Load", "config", "config/c.go", side="NEW")]
    c1 = [{"sha": "c1", "subject": "local: fix path traversal (CVE-2026-0001)", "body": "",
           "touches_candidates": ["r3"]},
          {"sha": "c2", "subject": "config: tidy", "body": "", "touches_candidates": ["r4"]}]
    r2 = [_cand("r1", "parseHeader", "proto", "proto/h.go"), _cand("r2", "Server.Serve", "srv", "srv/s.go")]
    ranges = {
        "GO-2026-0001": _range("GO-2026-0001", "github.com/o/r", "1.0.0", "1.0.1", r1, c1),
        "GO-2026-0002": _range("GO-2026-0002", "github.com/o/r", "1.0.0", "1.0.1", r1, c1),
        "GO-2026-0003": _range("GO-2026-0003", "github.com/o/r", "2.0.0", "2.0.1", r2, []),
        "GO-2026-0004": _range("GO-2026-0004", "github.com/o/r", "3.0.0", "3.0.1", [], [], status="EMPTY"),
    }
    vcs = {
        "GO-2026-0001": _vc("GO-2026-0001", "Path traversal when moving files in the local backend",
                            "cleanPath does not reject ..", "github.com/o/r", "1.0.0", "1.0.1", ["cleanPath"],
                            "2026-08-01", ["CVE-2026-0001"]),
        "GO-2026-0002": _vc("GO-2026-0002", "Listing directories follows symlinks", "", "github.com/o/r", "1.0.0",
                            "1.0.1", ["Local.List"], None),
        "GO-2026-0003": _vc("GO-2026-0003", "Header parsing panics on short input", "", "github.com/o/r", "2.0.0",
                            "2.0.1", ["NotAChangedFunction"], "2020-01-01"),  # gold outside the candidates
        "GO-2026-0004": _vc("GO-2026-0004", "Something", "", "github.com/o/r", "3.0.0", "3.0.1", ["F"], "2020-01-01"),
    }
    for cid, rr in ranges.items():
        (data / "release_range").mkdir(parents=True, exist_ok=True)
        (data / "candidate_code").mkdir(parents=True, exist_ok=True)
        (data / "release_range" / f"{cid}.json").write_text(json.dumps(rr))
        code = {"candidates": {c["candidate_id"]: {"package_name": "x", "doc": f"// {c['symbol']} does a thing.",
                                                   "signature": "", "body": BODIES[c["symbol"]],
                                                   "body_side": "NEW" if c["side"] == "NEW" else "OLD",
                                                   "file": (c["old_range"] or c["new_range"])["file"]}
                               for c in rr["candidates"]}, "complete": True}
        (data / "candidate_code" / f"{cid}.json").write_text(json.dumps(code))
    case_list = {"cases": [{"id": cid, "created": vcs[cid]["created"], "status": rr["status"]}
                           for cid, rr in ranges.items()]}
    return case_list, vcs, data


ALL_CONFIGS = ["random", "size", "bid", "bid-only", "bm25", "dense:fake", "hybrid:fake", "hybrid+rerank:fake+fake"]


def _run_all(tiny_d4, tmp_path, out):
    case_list, vcs, data = tiny_d4
    cases, ranges, notes = er.load_eval_set(case_list, vcs, data)
    h = er.Harness(cases, ranges, embedding_cache_root=tmp_path / "emb")
    cases_doc = er.cases_document(cases, ranges, notes)
    er.write_json(out / "cases.json", cases_doc)
    for name in ALL_CONFIGS:
        cfg = er.parse_config(name)
        for v in (["-"] if cfg.text_free else VARIANTS):
            run = h.run(cfg, v)
            run["environment"] = {"repo_commit": "test", "os": "test", "python": "3", "gpu": None}
            er.write_json(out / "runs" / er.run_file_name(name, run["variant"]), run)
    return cases, ranges, h


def test_harness_end_to_end_on_fakes(tiny_d4, tmp_path):
    out = tmp_path / "results"
    cases, ranges, h = _run_all(tiny_d4, tmp_path, out)
    assert len(ranges) == 3  # GO-2026-0001 and -0002 share one range (and one set of chunks)
    assert [c.cluster_key for c in cases][:2] == ["github.com/o/r@1.0.0..1.0.1"] * 2
    cases_doc, runs = load_results(out)
    assert len(runs) == 4 + 4 * 3
    s = Summaries(cases_doc, runs)
    by = {(r["config"], r["variant"]): i for i, r in enumerate(runs)}
    # B-ID: GO-2026-0001's own CVE id is in commit c1, which touches only r3 (cleanPath): rank 1.
    bid_rows = {row["id"]: row for row in runs[by[("bid", "-")]]["rows"]}
    assert bid_rows["GO-2026-0001"]["core"] == {"first_rank": 1, "top_ranks": [1]}
    assert runs[by[("bid-only", "-")]]["rows"][1]["core"]["first_rank"] is None  # 0002: no commit names it
    # Gold outside the candidate set and empty ranges are misses in (b), excluded from (a).
    assert s.summary(by[("bm25", "code_only")], "all", "a")["mrr"]["n"] == 2
    assert s.summary(by[("bm25", "code_only")], "all", "b")["mrr"]["n"] == 4
    for name in ("bm25", "dense:fake", "hybrid:fake", "hybrid+rerank:fake+fake"):
        assert by[(name, "code+commits_idmasked")] is not None

    doc = render_cp4_doc(out, "test")
    assert doc.startswith("# CP4 results: Mode 2 retrieval on D4")
    for section in ("## What retrieval can and cannot do here", "## Chunk variant `code_only`",
                    "denominator (b), n = 4", "denominator (a), n = 2", "### By candidate-set size",
                    "### By advisory date", "### Without the nine-case rclone cluster",
                    "## Paired differences against B-ID and random", "## Leakage control", "## Running time"):
        assert section in doc, section
    first_para = doc.split("\n\n")[2]
    assert "B-ID" in first_para


def test_harness_is_deterministic_and_embeds_each_text_once(tiny_d4, tmp_path):
    case_list, vcs, data = tiny_d4
    cases, ranges, _ = er.load_eval_set(case_list, vcs, data)
    h1 = er.Harness(cases, ranges, embedding_cache_root=tmp_path / "emb")
    a = h1.run(er.parse_config("hybrid+rerank:fake+fake"), "code+commits")
    calls_first = h1.embedder("fake").calls
    h2 = er.Harness(cases, ranges, embedding_cache_root=tmp_path / "emb")
    b = h2.run(er.parse_config("hybrid+rerank:fake+fake"), "code+commits")
    assert a["rows"] == b["rows"]
    # 6 chunk texts (4 in the shared range, 2 in the other; the shared range is embedded once)
    # + 3 queries (the EMPTY case has no candidates, so no query is embedded)
    assert calls_first == 6 + 3
    # A second harness re-embeds only the queries: every chunk text comes from the on-disk cache.
    assert h2.embedder("fake").calls == 3


def test_cli_eval_retrieval_and_render(tiny_d4, tmp_path, monkeypatch):
    case_list, vcs, data = tiny_d4
    cl = tmp_path / "D4_cases.json"
    cl.write_text(json.dumps(case_list))
    from vulntrace.dataset import datasets

    monkeypatch.setattr(datasets, "load_all_cases", lambda cache=None: (list(vcs.values()), 0))
    out = tmp_path / "res"
    rc = main(["eval", "retrieval", "--config", "bm25", "--config", "bid", "--variant", "code_only",
               "--cases", str(cl), "--data-dir", str(data), "--embedding-cache", str(tmp_path / "e"),
               "--out", str(out)])
    assert rc == 0
    assert sorted(p.name for p in (out / "runs").glob("*.json")) == ["bid__any.json", "bm25__code_only.json"]
    md = tmp_path / "doc.md"
    assert main(["results", "render", "--doc", "cp4", "--input", str(out), "--out", str(md)]) == 0
    assert "Not run yet:" in md.read_text()
    # A cases.json from different evidence is refused rather than silently mixed.
    doc = json.loads((out / "cases.json").read_text())
    doc["cases"][0]["n_candidates"] = 999
    (out / "cases.json").write_text(json.dumps(doc))
    assert main(["eval", "retrieval", "--config", "bm25", "--variant", "code_only", "--cases", str(cl),
                 "--data-dir", str(data), "--out", str(out)]) == 2


def test_missing_evidence_is_an_error_unless_allowed(tiny_d4, tmp_path):
    case_list, vcs, data = tiny_d4
    (data / "release_range" / "GO-2026-0003.json").unlink()
    with pytest.raises(er.HarnessError):
        er.load_eval_set(case_list, vcs, data)
    cases, _, notes = er.load_eval_set(case_list, vcs, data, allow_missing=True)
    assert notes["missing_evidence"] == ["GO-2026-0003"]
    assert [c.status for c in cases if c.case_id == "GO-2026-0003"] == ["MISSING"]
