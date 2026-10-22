"""E1, S1 and HyDE end to end on a tiny synthetic case set: fake LLM, fake embedder, in-memory
store, network blocked, no model library importable (CP5 deliverable 9)."""

import json
import socket
import sys

import pytest

from vulntrace.__main__ import main
from vulntrace.eval import hyde_eval, select_eval
from vulntrace.eval import retrieval as er
from vulntrace.models import fakes
from vulntrace.retrieval.chunking import VARIANT_CODE_COMMITS

from tests.integration.test_retrieval_harness import tiny_d4  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def no_network_no_models(monkeypatch):
    def refuse(*a, **kw):
        raise AssertionError("the CP5 pipeline tried to open a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    for mod in ("sentence_transformers", "torch", "transformers"):
        monkeypatch.setitem(sys.modules, mod, None)


def _harness(tiny_d4, tmp_path):
    case_list, vcs, data = tiny_d4
    cases, ranges, notes = er.load_eval_set(case_list, vcs, data)
    return cases, ranges, er.Harness(cases, ranges, embedding_cache_root=tmp_path / "emb")


# --- S1 -------------------------------------------------------------------------------------------
def test_s1_selection_beats_or_loses_to_top1_and_counts_every_status(tiny_d4, tmp_path):
    cases, ranges, h = _harness(tiny_d4, tmp_path)
    cfg = er.parse_config("hybrid:fake")

    def picks_gold(messages):  # select the candidate named cleanPath in the prompt, else abstain
        import re
        m = re.search(r"ID: (\S+)\nFunction: [^\n]*cleanPath", messages[1]["content"])
        return fakes.resp_select([m.group(1)]) if m else fakes.RESP_ABSTAIN

    doc = select_eval.run_s1(h, cfg, VARIANT_CODE_COMMITS, 10, fakes.FakeLLMClient(fallback=picks_gold))
    rows = {r["id"]: r for r in doc["rows"]}
    assert len(rows) == 4 and doc["counts"]["asked"] == 3 and doc["counts"]["not_asked"] == 1   # EMPTY range: no call
    g1 = rows["GO-2026-0001"]
    assert g1["m"]["llm"]["core"]["any_hit"] and g1["gold_in_topk"] and g1["llm"]["status"] == "VALID"
    # the gold of GO-2026-0003 is outside the candidate set: nobody can hit it
    g3 = rows["GO-2026-0003"]
    assert not g3["gold_in_topk"] and not g3["m"]["llm"]["core"]["any_hit"] and g3["llm"]["abstain"]
    assert rows["GO-2026-0004"]["llm"]["status"] == "NOT_ASKED" and rows["GO-2026-0004"]["m"]["llm"]["core"]["abstain"]
    c = doc["counts"]
    assert c["abstain"] == 1 and c["valid"] == 3 and c["invalid"] == 0
    # nothing committable carries prompts, code or raw text
    text = json.dumps(doc)
    assert "os.Rename" not in text and "Path traversal when moving" not in text


def test_s1_invalid_answers_are_scored_as_misses_and_reported(tiny_d4, tmp_path):
    cases, ranges, h = _harness(tiny_d4, tmp_path)
    doc = select_eval.run_s1(h, er.parse_config("bm25"), VARIANT_CODE_COMMITS, 5,
                             fakes.FakeLLMClient(fallback=lambda m: fakes.RESP_INJECTED))
    assert doc["counts"]["invalid"] == 3 and doc["counts"]["valid"] == 0 and doc["counts"]["calls"] == 6
    for r in doc["rows"]:
        assert r["m"]["llm"]["core"]["abstain"] and not r["m"]["llm"]["core"]["any_hit"]


def test_s1_aborts_when_the_server_is_down(tiny_d4, tmp_path):
    from vulntrace.models.llm import LLMError

    class Down(fakes.FakeLLMClient):
        def complete(self, *a, **k):
            raise LLMError("CONNECTION", "refused")

    cases, ranges, h = _harness(tiny_d4, tmp_path)
    with pytest.raises(select_eval.RunAborted):
        # GO-2026-0004 has no candidates (not asked), so only 3 cases call; make all of them fail
        select_eval.run_s1(h, er.parse_config("bm25"), VARIANT_CODE_COMMITS, 5, Down())


# --- HyDE -----------------------------------------------------------------------------------------
def test_hyde_variants_run_on_the_same_cases_and_restore_queries(tiny_d4, tmp_path):
    cases, ranges, h = _harness(tiny_d4, tmp_path)
    originals = [c.query for c in h.cases]
    client = fakes.FakeLLMClient(fallback=fakes.dry_run_text_responder)
    hyps = hyde_eval.generate_all(client, cases)
    cfgs = [er.parse_config("hybrid:fake"), er.parse_config("bm25")]
    runs = hyde_eval.run_hyde(h, cfgs, VARIANT_CODE_COMMITS, ["query+hyde", "hyde-only"], hyps)
    assert [(r["config"], r["hyde"]) for r in runs] == [(c, v) for c in ("hybrid:fake", "bm25")
                                                         for v in ("query", "query+hyde", "hyde-only")]
    assert [c.query for c in h.cases] == originals
    # `query` reproduces the plain CP4 run exactly (same ranks)
    plain = h.run(er.parse_config("bm25"), VARIANT_CODE_COMMITS)
    assert [r["rows"] for r in runs if (r["config"], r["hyde"]) == ("bm25", "query")][0] == plain["rows"]
    meta = hyde_eval.hyde_meta(client, cases, hyps)
    assert meta["counts"]["cases"] == 4 and meta["counts"]["empty"] == 0
    assert "func handle" not in json.dumps(meta)   # the hypothetical text is never written out


# --- CLI ------------------------------------------------------------------------------------------
@pytest.fixture
def cli_env(tiny_d4, tmp_path, monkeypatch):
    case_list, vcs, data = tiny_d4
    cl = tmp_path / "D4_cases.json"
    cl.write_text(json.dumps(case_list))
    from vulntrace.dataset import datasets

    monkeypatch.setattr(datasets, "load_all_cases", lambda cache=None: (list(vcs.values()), 0))
    base = ["--cases", str(cl), "--data-dir", str(data), "--embedding-cache", str(tmp_path / "e"),
            "--llm-cache", str(tmp_path / "llmc"), "--out", str(tmp_path / "res")]
    return base, tmp_path / "res"


def test_cli_select_release_dry_run(cli_env, capsys):
    base, out = cli_env
    assert main(["eval", "select", "--mode", "release", "--k", "5", "--dry-run", *base]) == 0
    doc = json.loads((out / "select_release__fake__k5.json").read_text())
    assert doc["model"]["dry_run"] and doc["model"]["kind"] == "FAKE" and doc["retriever"]["config"] == "hybrid:fake"
    assert doc["prompt"]["version"] == "root_cause_topk_v1" and len(doc["prompt"]["sha256"]) == 64
    assert "asked" in capsys.readouterr().out


def test_cli_hyde_dry_run_writes_cp4_format_runs(cli_env):
    base, out = cli_env
    assert main(["eval", "retrieval", "--hyde", "query+hyde", "--hyde", "hyde-only", "--dry-run", *base]) == 0
    d = out / "hyde__fake"
    assert sorted(p.name for p in (d / "runs").glob("*.json")) == [
        "bm25__hyde-hyde-only.json", "bm25__hyde-query-hyde.json", "bm25__hyde-query.json",
        "hybrid_fake__hyde-hyde-only.json", "hybrid_fake__hyde-query-hyde.json", "hybrid_fake__hyde-query.json"]
    from vulntrace.eval.retrieval_report import load_results

    cases_doc, runs = load_results(d)   # the CP4 loader accepts them unchanged
    assert len(runs) == 6 and {r["hyde"] for r in runs} == {"query", "query+hyde", "hyde-only"}


def test_cli_hyde_rejects_config_and_unknown_variant(cli_env):
    base, _ = cli_env
    assert main(["eval", "retrieval", "--hyde", "query+hyde", "--config", "bm25", "--dry-run", *base]) == 2
    assert main(["eval", "retrieval", "--hyde", "nonsense", "--dry-run", *base]) == 2


def test_cli_refuses_paid_endpoint(cli_env):
    base, out = cli_env
    assert main(["eval", "select", "--mode", "release", "--model", "llama3.1-8b", "--llm-url",
                 "https://api.openai.com/v1", *base]) == 2
    assert not out.exists()


def test_cli_refuses_empty_evidence(cli_env, tiny_d4):
    base, out = cli_env
    _, _, data = tiny_d4
    for p in (data / "release_range").glob("*.json"):
        p.unlink()
    assert main(["eval", "select", "--mode", "release", "--dry-run", *base]) == 2
    assert not out.exists()


# --- E1 -------------------------------------------------------------------------------------------
def _fix_ev(cid, cands):
    return {"case_id": cid, "status": "AVAILABLE" if cands else "EMPTY", "commits": [{"sha": "f", "parent_sha": "p"}],
            "candidates": [{"candidate_id": f"c{i}", "package_dir": "p", "symbol": s, "side": "BOTH",
                            "old_range": {"file": "p/f.go", "start": 1, "end": 2}, "new_range": None, "hunk_ids": [f"h{i}"]}
                           for i, s in enumerate(cands, start=1)],
            "hunks": [{"hunk_id": f"h{i}", "file": "p/f.go", "text": f"@@ -1 +1 @@\n-a{i}\n+b{i}"}
                      for i, _ in enumerate(cands, start=1)]}


def _d1_case(cid, core, derived=(), created="2026-01-01"):
    return {"id": cid, "aliases": [], "summary": f"summary {cid}", "details": "d", "created": created,
            "fix_commits": [{"host": "github.com", "owner": "o", "repo": "r", "sha": cid[-1] * 40}],
            "modules": [{"module": "m", "vulnerable_at": "1", "fixed_in": "2",
                         "packages": [{"package": "m", "core_symbols": core, "derived_symbols": list(derived)}]}]}


def test_e1_llm_vs_e0_on_synthetic_fix_evidence():
    ids = ["GO-1", "GO-2", "GO-3"]
    cases = {"GO-1": _d1_case("GO-1", ["A"]), "GO-2": _d1_case("GO-2", ["B"], ["C"]), "GO-3": _d1_case("GO-3", ["Z"])}
    ev = {"GO-1": _fix_ev("GO-1", ["A", "log", "helper"]), "GO-2": _fix_ev("GO-2", ["B", "C"]), "GO-3": _fix_ev("GO-3", [])}
    case_list = {"cases": [{"id": i, "created": "2026-01-01", "status": ev[i]["status"]} for i in ids]}

    def pick_first(messages):
        return fakes.resp_select(["c1"])

    doc = select_eval.run_e1(case_list, cases, ev, fakes.FakeLLMClient(fallback=pick_first))
    rows = {r["id"]: r for r in doc["rows"]}
    assert rows["GO-1"]["m"]["llm"]["core"]["exact"] and not rows["GO-1"]["m"]["e0"]["core"]["exact"]   # E0 predicts all 3
    assert rows["GO-1"]["m"]["e0"]["core"]["precision"] == pytest.approx(1 / 3)
    assert rows["GO-2"]["m"]["llm"]["core_derived"]["recall"] == 0.5     # chose B only; core ∪ derived = {B, C}
    assert rows["GO-3"]["llm"]["status"] == "NOT_ASKED" and rows["GO-3"]["m"]["e0"]["core"]["abstain"]
    assert doc["counts"]["asked"] == 2 and doc["max_selected"] == 5


# --- results document --------------------------------------------------------------------------------
def test_cp5_doc_renders_from_dry_run_files_with_the_fake_warning(cli_env):
    base, out = cli_env
    assert main(["eval", "select", "--mode", "release", "--k", "5", "--dry-run", *base]) == 0
    assert main(["eval", "retrieval", "--hyde", "query+hyde", "--hyde", "hyde-only", "--dry-run", *base]) == 0
    md = out.parent / "doc.md"
    assert main(["results", "render", "--doc", "cp5", "--input", str(out), "--out", str(md)]) == 0
    text = md.read_text()
    assert text.startswith("# CP5 results") and "WARNING: some results come from the FAKE LLM" in text
    for part in ("**Main finding.**", "## S1 (Mode 2, D4)", "## HyDE (Mode 2, D4)", "(a) gold inside the top-k",
                 "(b) all scored cases", "cutoff undocumented", "## Models, prompts, settings", "## Cost per case",
                 "Not run / not in this directory:** E1"):
        assert part in text, part
    assert "func handle" not in text  # no hypothetical text in the document


def test_cp5_doc_with_no_files_claims_nothing(tmp_path):
    from vulntrace.eval.llm_report import render_cp5_doc

    assert "nothing is claimed" in render_cp5_doc(tmp_path, "x")


def test_cp5_doc_for_e1_with_a_documented_cutoff_splits_pre_post_undated(tmp_path):
    import copy

    from vulntrace.eval.llm_report import render_cp5_doc

    ids = [f"GO-{i}" for i in range(6)]
    created = ["2020-01-01", "2024-02-01", "2024-03-01", None, "2025-01-01", "2019-01-01"]
    cases = {i: _d1_case(i, ["A"], created=c) for i, c in zip(ids, created)}
    ev = {i: _fix_ev(i, ["A", "x"]) for i in ids}
    case_list = {"cases": [{"id": i, "created": c, "status": "AVAILABLE"} for i, c in zip(ids, created)]}
    doc = select_eval.run_e1(case_list, cases, ev, fakes.FakeLLMClient(fallback=lambda m: fakes.resp_select(["c1"])))
    doc.update({"prompt": {"version": "root_cause_fix_v1", "sha256": "0" * 64}, "settings": {}, "environment": {},
                "model": {"alias": "m", "ollama_tag": "m:1", "params": "1B", "quantization": "q", "cutoff": "2023-12-31",
                           "cutoff_source": "test source", "model_digest": "abc", "dry_run": False, "kind": "REAL"}})
    d = tmp_path / "r"
    d.mkdir()
    (d / "select_fix__m.json").write_text(json.dumps(doc))
    text = render_cp5_doc(d, "x")
    assert "post-cutoff (created after 2023-12-31) - HEADLINE" in text and "n = 3 " in text      # 2024-02, 2024-03, 2025-01
    assert "pre-cutoff" in text and "undated (no created date)" in text
    assert "post-cutoff: 3; pre-cutoff: 2; undated: 1; total 6" in text
    assert "E0 (all changed functions)" in text and "WARNING" not in text
    assert "LLM vs E0 - F1:" in text
