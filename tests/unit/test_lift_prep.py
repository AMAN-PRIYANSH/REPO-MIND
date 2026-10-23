"""Source preparation for the lifting evaluation: module roots, synthesised go.mod, safe unpacking.
No network and no Go: git and go are replaced by fakes or not used."""

import io
import subprocess
import tarfile
from pathlib import Path

import pytest

from vulntrace.eval import lift_prep as lp


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_find_module_root_matches_the_module_line_and_prefers_the_shallowest(tmp_path):
    write(tmp_path / "go.mod", "module example.com/a\n\ngo 1.20\n")
    write(tmp_path / "sub" / "go.mod", "module example.com/a/sub\n")
    write(tmp_path / "v2" / "go.mod", "module example.com/a/v2\n")
    write(tmp_path / "vendor" / "x" / "go.mod", "module example.com/a\n")      # vendored copies are ignored
    write(tmp_path / "testdata" / "go.mod", "module example.com/a\n")
    assert lp.find_module_root(tmp_path, "example.com/a") == tmp_path
    assert lp.find_module_root(tmp_path, "example.com/a/sub") == tmp_path / "sub"
    assert lp.find_module_root(tmp_path, "example.com/a/v2") == tmp_path / "v2"
    assert lp.find_module_root(tmp_path, "example.com/other") is None


def test_find_module_root_accepts_a_quoted_module_path(tmp_path):
    write(tmp_path / "go.mod", 'module "example.com/q"\n')
    assert lp.find_module_root(tmp_path, "example.com/q") == tmp_path


@pytest.mark.parametrize("module,expected_dir", [
    ("github.com/o/r", ""), ("github.com/o/r/v3", ""), ("github.com/o/r/sub", "sub"), ("github.com/o/r/sub/v2", "sub")])
def test_synthesize_go_mod_for_a_tree_without_one(tmp_path, module, expected_dir):
    (tmp_path / "sub").mkdir()
    d = lp.synthesize_go_mod(tmp_path, module, "github.com/o/r")
    assert d == (tmp_path / expected_dir if expected_dir else tmp_path)
    assert (d / "go.mod").read_text(encoding="utf-8").startswith(f"module {module}\n")


@pytest.mark.parametrize("module", ["gopkg.in/yaml.v2", "github.com/o/other", "github.com/o/rx", "github.com/o/r/missing"])
def test_synthesize_go_mod_refuses_paths_that_are_not_in_this_repository(tmp_path, module):
    assert lp.synthesize_go_mod(tmp_path, module, "github.com/o/r") is None
    assert not list(tmp_path.rglob("go.mod"))


def make_tar(members: dict[str, bytes | tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, content in members.items():
            if isinstance(content, tuple):
                info = tarfile.TarInfo(name)
                info.type, info.linkname = tarfile.SYMTYPE, content[1]
                tf.addfile(info)
            else:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def fake_git(tar_bytes: bytes, rc: int = 0, err: bytes = b""):
    def runner(args, **kw):
        assert args[:3] == ["git", "archive", "--format=tar"]
        return subprocess.CompletedProcess(args, rc, stdout=tar_bytes, stderr=err)
    return runner


def test_extract_tree_unpacks_files(tmp_path):
    err = lp.extract_tree(tmp_path, "abc", tmp_path / "out", fake_git(make_tar({"a/b.go": b"package a\n"})))
    assert err is None and (tmp_path / "out" / "a" / "b.go").read_text() == "package a\n"


def test_extract_tree_does_not_write_outside_the_destination(tmp_path):
    evil = make_tar({"../escape.txt": b"x", "ok.txt": b"y"})
    lp.extract_tree(tmp_path, "abc", tmp_path / "out", fake_git(evil))
    assert not (tmp_path / "escape.txt").exists()


def test_an_unsafe_member_is_left_out_and_the_rest_is_unpacked(tmp_path):
    """CP5b: one absolute symlink in a test directory used to abort the whole unpack (NO_SOURCE)."""
    evil = make_tar({"testdata/link": ("sym", "/etc/passwd"), "../escape.txt": b"x", "ok.go": b"package a\n"})
    err = lp.extract_tree(tmp_path, "abc", tmp_path / "out", fake_git(evil))
    assert err is None
    assert (tmp_path / "out" / "ok.go").read_text() == "package a\n"
    assert not (tmp_path / "out" / "testdata" / "link").exists() and not (tmp_path / "escape.txt").exists()


def test_a_vendored_tree_is_not_tidied(tmp_path):
    tar = make_tar({"go.mod": b"module example.com/a\n", "vendor/modules.txt": b"# x\n", "a.go": b"package a\n"})
    seen = []

    def runner(args, **kw):
        seen.append(args[0])
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, stdout=tar, stderr=b"")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    r = lp.prepare_case(tmp_path, "abc", "example.com/a", tmp_path / "w", tmp_path / "m", runner)
    assert r["status"] == lp.READY and r["vendored"] is True and seen == ["git"]


def test_extract_tree_reports_a_git_error_as_one_line(tmp_path):
    err = lp.extract_tree(tmp_path, "abc", tmp_path / "out", fake_git(b"", rc=128, err=b"fatal: not a valid object name\nmore"))
    assert err == "git archive: fatal: not a valid object name"


def go_runner(rc=0, stderr="", seen=None):
    def runner(args, **kw):
        if seen is not None:
            seen.append((args, kw))
        return subprocess.CompletedProcess(args, rc, stdout="", stderr=stderr)
    return runner


def test_prepare_case_ready_uses_the_local_toolchain_and_never_runs_analysed_code(tmp_path):
    tar = make_tar({"go.mod": b"module example.com/a\n\ngo 1.20\n", "a.go": b"package a\n"})
    seen = []

    def runner(args, **kw):
        seen.append((args, kw))
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, stdout=tar, stderr=b"")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    r = lp.prepare_case(tmp_path, "abc", "example.com/a", tmp_path / "work", tmp_path / "gomod", runner, "example.com/a")
    assert r["status"] == lp.READY and r["module_rel"] == "" and r["synthesized_go_mod"] is False
    go_calls = [(a, k) for a, k in seen if a[0] == "go"]
    assert [a for a, _ in go_calls] == [["go", "mod", "tidy", "-e"]]            # no generate, no test, no run, no build
    env = go_calls[0][1]["env"]
    assert env["GOTOOLCHAIN"] == "local" and env["CGO_ENABLED"] == "0" and env["GOMODCACHE"] == str(tmp_path / "gomod")


def test_prepare_case_synthesises_go_mod_and_flags_it(tmp_path):
    tar = make_tar({"a.go": b"package a\n"})

    def runner(args, **kw):
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, stdout=tar, stderr=b"")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    r = lp.prepare_case(tmp_path, "abc", "github.com/o/r", tmp_path / "w", tmp_path / "m", runner, "github.com/o/r")
    assert r["status"] == lp.READY and r["synthesized_go_mod"] is True


def test_prepare_case_statuses(tmp_path):
    tar = make_tar({"a.go": b"package a\n"})
    git_ok = lambda args, **kw: subprocess.CompletedProcess(args, 0, stdout=tar, stderr=b"")  # noqa: E731
    no_mod = lp.prepare_case(tmp_path, "abc", "gopkg.in/x.v1", tmp_path / "w1", tmp_path / "m", git_ok, "github.com/o/r")
    assert no_mod["status"] == lp.NO_MODULE and "no go.mod" in no_mod["reason"]
    no_src = lp.prepare_case(tmp_path, "abc", "m", tmp_path / "w2", tmp_path / "m",
                             lambda args, **kw: subprocess.CompletedProcess(args, 128, stdout=b"", stderr=b"fatal: bad object"))
    assert no_src["status"] == lp.NO_SOURCE and "bad object" in no_src["reason"]

    tar2 = make_tar({"go.mod": b"module m\n\ngo 1.99\n"})

    def newer_go(args, **kw):
        if args[0] == "git":
            return subprocess.CompletedProcess(args, 0, stdout=tar2, stderr=b"")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="go: go.mod requires go >= 1.99 (running go 1.24.7; GOTOOLCHAIN=local)\n")

    r = lp.prepare_case(tmp_path, "abc", "m", tmp_path / "w3", tmp_path / "m", newer_go)
    assert r["status"] == lp.PREP_FAILED and "requires go >= 1.99" in r["reason"] and "\n" not in r["reason"]


def test_tidy_timeout_is_a_failure_line_not_a_crash(tmp_path):
    def runner(args, **kw):
        raise subprocess.TimeoutExpired(args, 1)

    assert "timed out" in lp.tidy(tmp_path, tmp_path / "m", runner, timeout=1)
