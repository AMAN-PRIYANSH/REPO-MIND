"""The CP5 Colab notebook: explains itself, calls only project code, stops on bad evidence or empty
results, keeps git and evidence on local disk, and every vulntrace command it runs parses."""

import json
import re
import shlex

from vulntrace.__main__ import build_parser
from vulntrace.paths import REPO_ROOT

NB = REPO_ROOT / "notebooks" / "cp5_llm_colab.ipynb"


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


def test_steps_in_order_with_local_disk_and_gates():
    src = _code()
    steps = ["git", "clone", 'pip install -q -e ".[ml]"', "materialize --set d1", "materialize --set d4", "evidence_gate",
             "index build --set d4", "\"serve\"", "ollama\", \"pull", "eval select --mode fix", "eval select --mode release",
             "eval retrieval --hyde", "results render --doc cp5", "zipfile"]
    positions = [src.index(s) for s in steps]
    assert positions == sorted(positions)
    assert 'DATA = "/content/data"' in src and 'CACHE = "/content/cache"' in src
    assert 'os.environ["VULNTRACE_CACHE"] = CACHE' in src and "WORK}/cache" not in src and "WORK}/data" not in src
    assert src.count("raise SystemExit") >= 2           # evidence gate and the refuse-empty zip
    assert "OLLAMA_HOST=\"127.0.0.1:11434\"" in src.replace("'", '"') or 'OLLAMA_HOST="127.0.0.1:11434"' in src
    assert "Timings" in src                              # running time per step is recorded


def test_at_most_two_models_and_known_aliases():
    from vulntrace.llm.models_config import MODELS

    m = re.search(r"^MODELS = (\[.*?\])", _code(), flags=re.M).group(1)
    aliases = json.loads(m.replace("'", '"'))
    assert 1 <= len(aliases) <= 2 and set(aliases) <= set(MODELS)


def test_every_vulntrace_command_in_the_notebook_parses():
    ns = {"DATA": "/d", "WORK": "/w", "OUT": "/o", "DRY": "--dry-run", "DEVICE": "cuda", "LLM_CACHE": "/c", "m": "fake", "k": 10}
    parser = build_parser()
    seen = 0
    for line in _code().splitlines():
        mt = re.match(r"\s*!python (?:-u )?-m vulntrace (.*)$", line)
        if not mt:
            continue
        argv = shlex.split(mt.group(1).format(**ns))
        parser.parse_args(argv)
        seen += 1
    assert seen >= 10
