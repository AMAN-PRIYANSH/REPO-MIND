"""The agent tests skip when the [agent] extra (langgraph) is not installed. In CI that would hide
them, so there a missing langgraph is a failure (GitHub Actions sets CI=true)."""

import importlib.util
import os

import pytest


@pytest.mark.skipif(os.environ.get("CI") != "true", reason="only enforced in CI")
def test_ci_installs_the_agent_extra():
    assert importlib.util.find_spec("langgraph") is not None, "CI must install .[agent] so the agent tests run"
