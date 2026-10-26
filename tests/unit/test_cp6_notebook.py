"""The CP6 Colab notebook: explains itself, calls only project code, keeps git and evidence on local disk,
stops on bad evidence or missing results, checks that Ollama really generates, resumes from Drive, and
every vulntrace command it runs parses."""

import json
import re
import shlex

from vulntrace.__main__ import build_parser
from vulntrace.paths import REPO_ROOT

NB = REPO_ROOT / "notebooks" / "cp6_agent_colab.ipynb"


def _cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def _code():
    return "\n".join("".join(c["source"]) for c in _cells() if c["cell_type"] == "code")


def test_every_code_cell_starts_with_an_explaining_comment():
    for cell in _cells():
        if cell["cell_type"] == "code":
            assert "".join(cell["source"]).lstrip().startswith("#"), "".join(cell["source"])[:80]


def test_no_outputs_and_no_paid_api():
    text = NB.read_text(encoding="utf-8").lower()
    for cell in _cells():
        assert cell.get("outputs", []) == []
    for bad in ("openai", "anthropic", "api_key", "gemini", "cohere", "api.groq", "openrouter"):
        assert bad not in text


def test_steps_in_order_with_local_disk_gates_and_resume():
    src = _code()
    steps = ["git\", \"clone", 'pip install -q -e ".[ml,agent]"', "materialize --set d4", "evidence_gate", "agent prepare --set d4 --diffs",
             "agent prepare --set d4 --graph", "compare_with_summary", "tarfile.open(tmp, \"w:gz\")", "index build --set d4", "\"serve\"",
             "ollama\", \"pull", "ollama_setup.ensure_working", "eval symbols --strategy agent", "results render --doc cp6",
             "zipfile.ZipFile(zpath"]
    positions = [src.index(s) for s in steps]
    assert positions == sorted(positions)
    assert 'DATA = "/content/data"' in src and 'CACHE = "/content/cache"' in src
    assert 'os.environ["VULNTRACE_CACHE"] = CACHE' in src and "WORK}/cache" not in src and "WORK}/data" not in src
    assert 'TRACES = f"{WORK}/traces' in src and '--trace-dir "{TRACES}"' in src      # traces on Drive: a disconnect resumes
    assert 'LLM_CACHE = f"{WORK}/llm_cache' in src
    assert src.count("raise SystemExit") >= 4           # gate, unsafe zip member, pull failure, unfinished part
    assert 'OLLAMA_HOST="127.0.0.1:11434"' in src.replace("'", '"')
    assert "Timings" in src


def test_restored_evidence_passes_the_same_gate_and_is_extracted_safely():
    src = _code()
    assert src.index('tf.extractall(DATA, filter="data")') < src.index("evidence_gate.check_evidence")
    assert src.index("materialize --set d4") < src.index("evidence_gate.check_evidence")
    assert "REBUILD_EVIDENCE = False" in src and "if not RESTORED:" in src   # diffs come from the archive when restored


def test_install_is_checked_with_a_generate_call_and_can_be_repaired():
    src = _code()
    assert "def reinstall_ollama" in src and "probe_generate" in src
    assert src.index('"pull"') < src.index("ollama_setup.ensure_working") < src.index("eval symbols --strategy agent")


def test_four_parts_cover_every_arm_and_model_exactly_once():
    from vulntrace.eval.agent_eval import ARMS
    from vulntrace.llm.models_config import MODELS

    src = _code()
    models = json.loads(re.search(r"^MODELS = (\[.*?\])", src, flags=re.M).group(1))
    assert sorted(models) == ["llama3.1-8b", "qwen2.5-coder-7b"] and set(models) <= set(MODELS)
    arms = json.loads(re.search(r"^ARMS = (\[.*?\])", src, flags=re.M).group(1))
    assert arms == ["A2", "A3"] and set(arms) == set(ARMS)
    parts = eval(re.search(r"^PARTS = (\{.*?\})$", src, flags=re.M).group(1))
    assert sorted(parts) == [1, 2, 3, 4] and sorted(parts.values()) == sorted((a, m) for a in arms for m in models)
    assert [parts[p][0] for p in (1, 2)] == ["A2", "A2"]        # the main comparison runs first
    assert re.search(r"^PART = [1-4]$", src, flags=re.M) and "ARM, MODEL = PARTS[PART]" in src
    assert "--arm {ARM} --model {RUN_MODEL}" in src and src.count("eval symbols --strategy agent") == 1


def test_every_vulntrace_command_in_the_notebook_parses():
    ns = {"DATA": "/d", "WORK": "/w", "OUT": "/o", "DRY": "--dry-run", "DEVICE": "cuda", "LLM_CACHE": "/c", "m": "fake",
          "arm": "A2", "EMB": "/e", "TRACES": "/t", "LIM": "--limit 3",
          "ARM": "A2", "RUN_MODEL": "llama3.1-8b"}
    parser = build_parser()
    seen = 0
    for line in _code().splitlines():
        mt = re.match(r"\s*!python (?:-u )?-m vulntrace (.*)$", line)
        if not mt:
            continue
        parser.parse_args(shlex.split(mt.group(1).format(**ns)))
        seen += 1
    assert seen >= 9


def test_branch_is_this_checkpoints_branch():
    # CP6 is approved, so STATUS.md has moved on; the CP6 report is the frozen record of its branches.
    report = (REPO_ROOT / "docs" / "progress" / "reports" / "CP6_REPORT.md").read_text(encoding="utf-8")
    branch = re.search(r'^BRANCH = "([^"]+)"', _code(), flags=re.M).group(1)
    assert f"`{branch}`" in report
