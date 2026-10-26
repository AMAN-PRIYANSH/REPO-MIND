"""CP6 deliverable 2 / criterion 2: the agent prompt templates are versioned files, frozen before the
first real run. Editing a frozen file fails this test; a change is a new `_vN` file (and prompt set),
reported as a separate post-hoc row, never replacing v1."""

import hashlib
import json
import re
from importlib import resources

from vulntrace.agent import prompts as AP


def _dir():
    return resources.files("vulntrace.agent").joinpath("prompts")


def test_every_agent_template_is_listed_and_unchanged():
    frozen = json.loads(_dir().joinpath("FROZEN.json").read_text(encoding="utf-8"))
    files = sorted(p.name for p in _dir().iterdir() if p.name.endswith(".txt"))
    assert files == sorted(frozen["sha256"]), "a template is missing from FROZEN.json (or listed but absent)"
    for name in files:
        assert hashlib.sha256(_dir().joinpath(name).read_bytes()).hexdigest() == frozen["sha256"][name], \
            f"{name} was edited after the freeze: create a new _vN file instead and report it as a post-hoc row"
        assert re.search(r"_v\d+\.txt$", name)
    assert frozen["prompt_set"] == AP.PROMPT_SET


def test_code_uses_exactly_the_frozen_templates():
    frozen = json.loads(_dir().joinpath("FROZEN.json").read_text(encoding="utf-8"))["sha256"]
    assert sorted(f"{n}.txt" for n in AP.ALL_TEMPLATES) == sorted(frozen)
    for name in AP.ALL_TEMPLATES:
        assert AP.template_text(name).strip()
