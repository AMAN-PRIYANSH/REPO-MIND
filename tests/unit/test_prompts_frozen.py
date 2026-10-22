"""CP5 deliverable 3/criterion 7: prompt templates are versioned files, frozen before the first real
run. Editing a frozen file fails this test; a change is a new `_vN` file plus an entry here and in
the report."""

import hashlib
import json
import re
from importlib import resources

from vulntrace.llm import prompts


def _dir():
    return resources.files("vulntrace.llm").joinpath("prompts")


def test_every_template_is_listed_and_unchanged():
    frozen = json.loads(_dir().joinpath("FROZEN.json").read_text(encoding="utf-8"))["sha256"]
    files = sorted(p.name for p in _dir().iterdir() if p.name.endswith(".txt"))
    assert files == sorted(frozen), "a template is missing from FROZEN.json (or listed but absent)"
    for name in files:
        assert hashlib.sha256(_dir().joinpath(name).read_bytes()).hexdigest() == frozen[name], \
            f"{name} was edited after the freeze: create a new _vN file instead and record the reason in the report"
        assert re.search(r"_v\d+\.txt$", name)


def test_code_references_existing_template_versions():
    for name in (prompts.SYSTEM_PROMPT, prompts.FIX_PROMPT, prompts.TOPK_PROMPT, prompts.RETRY_PROMPT,
                 prompts.HYDE_PROMPT, prompts.HYDE_SYSTEM_PROMPT):
        assert prompts.template_text(name).strip()
        assert re.search(r"_v\d+$", name)
