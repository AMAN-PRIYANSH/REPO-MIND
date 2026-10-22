"""CP5 task 0b: every Colab notebook puts the checkout on sys.path right after `pip install -e`
(the notebook kernel does not see a fresh editable install until restarted), before any
in-kernel `import vulntrace`."""

import json

from vulntrace.paths import REPO_ROOT


def _notebooks():
    return sorted((REPO_ROOT / "notebooks").glob("*.ipynb"))


def test_there_are_notebooks():
    assert _notebooks()


def test_sys_path_line_follows_install_before_first_vulntrace_import():
    for nb in _notebooks():
        code = ["".join(c["source"]) for c in json.loads(nb.read_text(encoding="utf-8"))["cells"]
                if c["cell_type"] == "code"]
        src = "\n".join(code)
        install = src.index("pip install -q -e")
        path_line = src.index('sys.path.insert(0, "/content/REPO-MIND/src")')
        invalidate = src.index("importlib.invalidate_caches()")
        assert install < path_line < invalidate, nb.name
        first_import = min(i for i in (src.find("from vulntrace"), src.find("import vulntrace")) if i >= 0)
        assert invalidate < first_import, nb.name
