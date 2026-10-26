"""CP6 end to end on a tiny synthetic D4: fake LLM, fake embedder, in-memory store, network blocked,
no model library importable (deliverable 6). Also the agent evidence step on a real local git
repository, and the closed pool of the world built from evidence."""

import json
import re
import socket
import subprocess
import sys

import pytest

pytest.importorskip("langgraph", reason="the agent needs the [agent] extra (langgraph); CI installs it")

from vulntrace.__main__ import main  # noqa: E402
from vulntrace.agent import budget as B  # noqa: E402
from vulntrace.agent import prepare  # noqa: E402
from vulntrace.eval import agent_eval  # noqa: E402
from vulntrace.eval import retrieval as er  # noqa: E402
from vulntrace.models import fakes  # noqa: E402
from vulntrace.retrieval.chunking import VARIANT_CODE_COMMITS  # noqa: E402

from tests.integration.test_retrieval_harness import tiny_d4  # noqa: E402,F401  (fixture)


@pytest.fixture(autouse=True)
def no_network_no_models(monkeypatch):
    def refuse(*a, **kw):
        raise AssertionError("the CP6 pipeline tried to open a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    for mod in ("sentence_transformers", "torch", "transformers"):
        monkeypatch.setitem(sys.modules, mod, None)


def _harness(tiny_d4, tmp_path):
    case_list, vcs, data = tiny_d4
    cases, ranges, notes = er.load_eval_set(case_list, vcs, data)
    return cases, er.Harness(cases, ranges, embedding_cache_root=tmp_path / "emb"), data


def picks_clean_path(messages):
    """Reads the IDs the agent has seen; submits the one named cleanPath if shown, else abstains."""
    text = "\n".join(m["content"] for m in messages if m["role"] == "user")
    m = re.search(r"\[(r\d+)\] [^\n|]*cleanPath", text)
    if m:
        return fakes.action("submit_answer", candidate_ids=[m.group(1)], evidence=[m.group(1)])
    return fakes.action("submit_answer", abstain=True)


def test_rank_query_equals_rank_case_for_the_advisory_and_does_not_pollute_its_cache(tiny_d4, tmp_path):
    cases, h, _ = _harness(tiny_d4, tmp_path)
    cfg = er.parse_config("hybrid:fake")
    for case in cases:
        before = h.rank_case(cfg, case, VARIANT_CODE_COMMITS)
        assert h.rank_query(cfg, case, VARIANT_CODE_COMMITS, case.query) == before
        other = h.rank_query(cfg, case, VARIANT_CODE_COMMITS, "readDir List directories")
        assert sorted(other) == sorted(case.candidate_ids)
        assert h.rank_case(cfg, case, VARIANT_CODE_COMMITS) == before   # cached advisory ranking unchanged
    g1 = cases[0]
    assert h.rank_query(cfg, g1, VARIANT_CODE_COMMITS, "readDir List directories")[0] == "r2"


def test_world_is_the_cases_closed_pool_without_gold(tiny_d4, tmp_path):
    cases, h, data = _harness(tiny_d4, tmp_path)
    cfg = er.parse_config("hybrid:fake")
    w = agent_eval.build_world(h, cfg, VARIANT_CODE_COMMITS, cases[0], data, graph=True)
    assert set(w.candidates) == set(cases[0].candidate_ids) and w.initial_ranking == h.rank_case(cfg, cases[0],
                                                                                                VARIANT_CODE_COMMITS)
    assert not any("gold" in k for k in vars(w)) and w.graph is None and "not prepared" in w.graph_note
    assert [c.sha for c in w.commits] == ["c1", "c2"] and w.candidates["r3"].start == 1


def test_run_arm_scores_rows_and_resumes_from_traces(tiny_d4, tmp_path):
    cases, h, data = _harness(tiny_d4, tmp_path)
    cfg = er.parse_config("hybrid:fake")
    client = fakes.FakeLLMClient(fallback=picks_clean_path)
    doc = agent_eval.run_arm(h, cfg, VARIANT_CODE_COMMITS, "A2", client, "fake", data, tmp_path / "traces")
    rows = {r["id"]: r for r in doc["rows"]}
    assert doc["counts"]["run"] == 3 and rows["GO-2026-0004"]["stop_reason"] == B.NOT_RUN   # EMPTY range: not run
    g1 = rows["GO-2026-0001"]
    assert g1["stop_reason"] == B.SUBMITTED and g1["answer"] == ["r3"] and g1["gold_ids"] == ["r3"]
    assert g1["gold_in_candidates"] and len(g1["a0_top3"]) == 3 and g1["answer_ids_seen"]
    assert not rows["GO-2026-0003"]["gold_in_candidates"]   # gold outside the candidates: a miss for every arm
    text = json.dumps(doc)
    assert "os.Rename" not in text and "Path traversal when moving" not in text   # no code, no advisory text
    assert len(list((tmp_path / "traces" / "A2__fake").glob("*.json.gz"))) == 3
    again = agent_eval.run_arm(h, cfg, VARIANT_CODE_COMMITS, "A2", client, "fake", data, tmp_path / "traces")
    assert again["counts"]["reused_traces"] == 3
    strip = lambda rs: [{k: v for k, v in r.items() if k not in ("reused_trace", "wall_seconds")} for r in rs]  # noqa: E731
    assert strip(again["rows"]) == strip(doc["rows"])
    # another budget is another configuration: nothing is reused
    other = agent_eval.run_arm(h, cfg, VARIANT_CODE_COMMITS, "A2", client, "fake", data, tmp_path / "traces",
                               budget=B.Budget(max_steps=5))
    assert other["counts"]["reused_traces"] == 0


def test_run_arm_aborts_when_the_server_is_down(tiny_d4, tmp_path):
    from vulntrace.models.llm import LLMError

    cases, h, data = _harness(tiny_d4, tmp_path)

    def down(messages):
        raise LLMError("CONNECTION", "refused")

    with pytest.raises(agent_eval.RunAborted):
        agent_eval.run_arm(h, er.parse_config("hybrid:fake"), VARIANT_CODE_COMMITS, "A2",
                           fakes.FakeLLMClient(fallback=down), "fake", data, tmp_path / "t")


# --- CLI -----------------------------------------------------------------------------------------------
@pytest.fixture
def cli_env(tiny_d4, tmp_path, monkeypatch):
    case_list, vcs, data = tiny_d4
    cl = tmp_path / "D4_cases.json"
    cl.write_text(json.dumps(case_list))
    from vulntrace.dataset import datasets

    monkeypatch.setattr(datasets, "load_all_cases", lambda cache=None: (list(vcs.values()), 0))
    base = ["--cases", str(cl), "--data-dir", str(data), "--embedding-cache", str(tmp_path / "e"),
            "--llm-cache", str(tmp_path / "llmc"), "--out", str(tmp_path / "res")]
    return base, tmp_path / "res", data


def test_cli_agent_dry_run_writes_both_arms_and_traces(cli_env, capsys):
    base, out, data = cli_env
    assert main(["eval", "symbols", "--strategy", "agent", "--set", "d4", "--dry-run", *base]) == 0
    for arm in ("A2", "A3"):
        doc = json.loads((out / f"agent__{arm}__fake.json").read_text())
        assert doc["model"]["dry_run"] and doc["dry_run"] and doc["retriever"]["config"] == "hybrid:fake"
        assert doc["prompt"]["set"] == "agent_v1" and len(doc["prompt"]["sha256"]) == 64
        assert doc["config"]["budget"] == B.Budget().as_dict() and doc["langgraph_version"]
        assert doc["counts"]["run"] == 3 and doc["agent_evidence"]["graph"]["available"] == 0
    traces = sorted((data / "agent_traces").glob("*/*.json.gz"))
    assert len(traces) == 6
    printed = capsys.readouterr().out
    assert "A2 [fake]: 3 run" in printed and "A3 [fake]: 3 run" in printed
    assert main(["agent", "show-trace", "--trace", str(traces[0]), "--data-dir", str(data)]) == 0
    shown = capsys.readouterr().out
    assert "initial search showed" in shown and "=" in shown


def test_cli_agent_rejects_bad_input(cli_env):
    base, out, data = cli_env
    assert main(["eval", "symbols", "--strategy", "agent", "--dry-run", *base]) == 2                     # no --set
    assert main(["eval", "symbols", "--strategy", "agent", "--set", "d4", "--arm", "A1", "--dry-run", *base]) == 2
    assert main(["eval", "symbols", "--strategy", "agent", "--set", "d4", "--model", "llama3.1-8b", "--llm-url",
                 "https://api.anthropic.com/v1", *base]) == 2
    for p in (data / "release_range").glob("*.json"):
        p.unlink()
    assert main(["eval", "symbols", "--strategy", "agent", "--set", "d4", "--dry-run", *base]) == 2
    assert not out.exists()


# --- agent evidence: commit diffs from a real local git repository ---------------------------------------
def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@e", "HOME": str(repo), "PATH": "/usr/bin:/bin"})
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def test_commit_diff_shows_go_files_non_test_first_without_vendor(tmp_path):
    repo = tmp_path / "repo"
    (repo / "p").mkdir(parents=True)
    (repo / "vendor" / "x").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "p" / "a.go").write_text("package p\n\nfunc A() {}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / "p" / "a.go").write_text("package p\n\nfunc A() { check() }\n")
    (repo / "p" / "a_test.go").write_text("package p\n\nfunc TestA() {}\n")
    (repo / "vendor" / "x" / "v.go").write_text("package x\n")
    (repo / "README.md").write_text("docs\n")
    _git(repo, "add", ".")
    sha = _git(repo, "commit", "-q", "-m", "fix")
    d = prepare.commit_diff(repo, sha)
    assert d["error"] is None and "func A() { check() }" in d["diff"]
    assert d["diff"].index("p/a.go") < d["diff"].index("p/a_test.go")
    assert "vendor/x/v.go" not in d["diff"] and "README" not in d["diff"]
    bad = prepare.commit_diff(repo, "0" * 40)
    assert bad["diff"] is None and bad["error"].startswith("git show:")


def test_neighbour_table_from_recorded_helper_response():
    from pathlib import Path

    from vulntrace.methods import lift as lift_method

    resp = json.loads((Path(__file__).parents[1] / "contract" / "responses_cp5b" / "callees_one_hop.json").read_text())
    targets = [r["target"] for r in resp["results"]]
    recs = lift_method.to_neighbor_records("callees", targets, resp, None, 5)
    nodes = {("vtlift/diamond", "Top"): "r1", ("vtlift/interface_call", "Do"): "r2", ("vtlift/diamond", "Left"): "r3"}
    table = prepare.table_from_records(nodes, {"callees": recs})
    assert table["r1"]["status"] == "FOUND" and [e["candidate_id"] for e in table["r1"]["callees"]] == ["r3", None]
    assert table["r2"]["callees"][0]["kind"] == "DYNAMIC" and table["r2"]["callees"][0]["line"] == 12
    from vulntrace.methods.helper import HelperError

    err = lift_method.to_neighbor_records("callers", targets, None, HelperError("TIMEOUT", "slow"), 1)
    table = prepare.table_from_records(nodes, {"callees": recs, "callers": err})
    assert table["r1"]["status"] == "ERROR TIMEOUT" and table["r1"]["callees"]   # a problem in one direction wins
