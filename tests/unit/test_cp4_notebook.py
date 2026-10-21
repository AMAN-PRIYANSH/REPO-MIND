"""The Colab notebook (CP4 D7): every code cell explains itself, it only calls project code,
the grid parses and stays within Q6, and the dry-run grid uses only fakes."""

import json
import re

from vulntrace.eval import cp4_plan
from vulntrace.eval.retrieval import parse_config
from vulntrace.paths import REPO_ROOT

NB = REPO_ROOT / "notebooks" / "cp4_retrieval_colab.ipynb"


def _cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def test_every_code_cell_starts_with_an_explaining_comment():
    for cell in _cells():
        if cell["cell_type"] == "code":
            assert "".join(cell["source"]).lstrip().startswith("#"), "".join(cell["source"])[:80]


def test_notebook_has_no_outputs_and_no_paid_api():
    text = NB.read_text(encoding="utf-8").lower()
    for cell in _cells():
        assert cell.get("outputs", []) == []
    for bad in ("openai", "anthropic", "api_key", "gemini", "cohere"):
        assert bad not in text


def test_notebook_steps_are_present_in_order():
    src = "\n".join("".join(c["source"]) for c in _cells() if c["cell_type"] == "code")
    steps = ["git", "clone", "pip install -q -e \".[ml]\"", "dataset materialize --set d4", "check_embedder",
             "index build --set d4", "eval retrieval", "results render --doc cp4", "zipfile"]
    positions = [src.index(s) for s in steps]
    assert positions == sorted(positions)
    assert re.search(r"--data-dir \"\{WORK\}/data\"", src)  # cached on Drive (resumable)


def test_plan_configs_parse_and_respect_q6():
    for gpu in (True, False):
        for group in cp4_plan.configs(gpu=gpu):
            for name in group:
                parse_config(name)
    assert len(cp4_plan.EMBEDDERS) <= 2 and len(cp4_plan.RERANKERS) <= 2
    cpu = [c for g in cp4_plan.configs(gpu=False) for c in g]
    assert not any("rerank" in c for c in cpu) and not any("codesearch" in c for c in cpu)
    full = [c for g in cp4_plan.configs(gpu=True) for c in g]
    assert {"bm25", "bid", "random", "dense:bge-small", "dense:codesearch",
            "hybrid+rerank:codesearch+bge-reranker"} <= set(full)


def test_dry_run_grid_uses_only_fakes():
    dry = [c for g in cp4_plan.configs(gpu=True, dry_run=True) for c in g]
    assert dry == list(dict.fromkeys(dry))  # no duplicates
    for name in dry:
        cfg = parse_config(name)
        assert cfg.embedder in (None, "fake") and cfg.reranker in (None, "fake")
    assert "hybrid+rerank:fake+fake" in dry
