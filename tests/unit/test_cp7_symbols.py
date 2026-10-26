"""CP7 target-symbol selection: Mode 1 analyses every changed non-test function; Mode 2 the top-k."""

from tests.unit.cp7_support import LIB, fix_evidence, release_range
from vulntrace.pipeline import symbols as sy


def test_import_path_for():
    assert sy.import_path_for("m.com/x", "", "") == "m.com/x"
    assert sy.import_path_for("m.com/x", "", "a/b") == "m.com/x/a/b"
    assert sy.import_path_for("m.com/x/v2", "v2", "v2/a") == "m.com/x/v2/a"
    assert sy.import_path_for("m.com/x/sub", "sub", "other/a") is None


def test_module_rel_for_uses_cp3_rule():
    fc = {"owner": "o", "repo": "r"}
    assert sy.module_rel_for("github.com/o/r", fc) == ""
    assert sy.module_rel_for("github.com/o/r/sub/v3", fc) == "sub"
    assert sy.module_rel_for("golang.org/x/net", {"owner": "golang", "repo": "net"}) == ""
    assert sy.module_rel_for("github.com/o/r", None) == ""


def test_mode1_analyses_every_changed_function_that_existed_before_the_fix():
    fe = fix_evidence([("a", "F", "BOTH"), ("a", "T.M", "OLD"), ("b", "G", "BOTH"), ("a", "Added", "NEW")])
    targets, nc = sy.mode1_symbols(fe, LIB, "")
    assert [(t["package"], t["symbol"]) for t in targets] == [(f"{LIB}/a", "F"), (f"{LIB}/a", "T.M"), (f"{LIB}/b", "G")]
    assert all(t["origin"] == "FIX_CHANGED" and t["decides_verdict"] for t in targets)
    assert [(n["symbol"], n["reason"]) for n in nc] == [("Added", "ADDED_BY_FIX")]


def test_mode1_outside_module_is_not_covered_not_dropped():
    fe = fix_evidence([("sub/a", "F", "BOTH"), ("tools/x", "G", "BOTH")])
    targets, nc = sy.mode1_symbols(fe, "github.com/o/r/sub", "sub")
    assert [t["package"] for t in targets] == ["github.com/o/r/sub/a"]
    assert [(n["symbol"], n["reason"]) for n in nc] == [("G", "OUTSIDE_MODULE")]


def test_context_only_flag():
    fe = fix_evidence([("a", "F", "BOTH")])
    # the hunk's change is on line 10 (inside 10..20): changed
    assert sy.mode1_symbols(fe, LIB, "")[0][0]["context_only"] is False
    # a neighbour whose range only covers the hunk's context lines
    fe["candidates"][0]["old_range"] = {"file": "a/f1.go", "start": 1, "end": 9}
    fe["candidates"][0]["new_range"] = {"file": "a/f1.go", "start": 1, "end": 9}
    assert sy.mode1_symbols(fe, LIB, "")[0][0]["context_only"] is True


def test_changed_lines():
    h = {"old_start": 5, "new_start": 5, "text": " a\n-b\n-c\n+d\n e\n+f\n\\ No newline at end of file"}
    assert sy.changed_lines(h) == ({6, 7}, {6, 8})


def test_mode2_top_k_with_rank_and_score():
    rr, _ = release_range([("", "A", "BOTH"), ("", "B", "BOTH"), ("", "C", "NEW"), ("", "D", "BOTH")])
    ranked = [("r3", 0.9), ("r2", 0.8), ("r1", 0.5), ("r4", 0.1)]
    targets, nc = sy.mode2_symbols(rr, ranked, 3, LIB, "")
    assert [(t["symbol"], t["rank"], t["score"], t["origin"]) for t in targets] == [
        ("B", 2, 0.8, "RANKED_CANDIDATE"), ("A", 3, 0.5, "RANKED_CANDIDATE")]
    assert sorted((n["symbol"], n["reason"], n["rank"]) for n in nc) == [("C", "ADDED_BY_FIX", 1), ("D", "BEYOND_TOP_K", 4)]


def test_given_symbols_dedupe():
    t = sy.given_symbols([{"package": "p", "symbol": "F"}, {"package": "p", "symbol": "F"}], "FIXTURE")
    assert len(t) == 1 and t[0]["origin"] == "FIXTURE"
