"""CP7 verifier: pure structural and call-site checks."""

from tests.unit.cp7_support import GOOD_PATH, LIB, MAIN_PKG, TARGET, path
from vulntrace.verifier import checks as ck


def test_symbol_forms():
    assert ck.normalise_symbol("(*T).M") == "T.M"
    assert ck.normalise_symbol("*T.M") == "T.M"
    assert ck.normalise_symbol("ParseAny[T]") == "ParseAny"
    assert ck.normalise_symbol("List[T].Push") == "List.Push"
    assert ck.declared_name("p.main$1$2") == "p.main"
    assert ck.declared_name("p.init#3") == "p.init"
    assert ck.declared_name("p.apply[string]") == "p.apply"
    assert ck.declared_name("p.Impl.Run$bound") == "p.Impl.Run"
    assert ck.declared_name("p.F[a/b.T]") == "p.F"


def test_good_structure():
    assert ck.check_structure(GOOD_PATH, MAIN_PKG, TARGET) == []


def test_structure_failures():
    assert ck.check_structure(GOOD_PATH, "example.com/app/cmd/other", TARGET)          # wrong main package
    bad = path(MAIN_PKG, TARGET, [(f"{LIB}.Parse", "cmd/a/main.go", 4)], entry="helper")
    assert ck.check_structure(bad, MAIN_PKG, TARGET)                                     # entry is not main/init
    chain = path(MAIN_PKG, TARGET, [("x.A", "f.go", 1), (f"{LIB}.Parse", "f.go", 2)])
    chain["edges"][1]["caller"] = "x.B"
    assert any("does not continue" in f.reason for f in ck.check_structure(chain, MAIN_PKG, TARGET))
    wrong_end = path(MAIN_PKG, TARGET, [(f"{LIB}.Safe", "cmd/a/main.go", 4)])
    assert any("is not the target" in f.reason for f in ck.check_structure(wrong_end, MAIN_PKG, TARGET))
    other_target = path(MAIN_PKG, {"package": LIB, "symbol": "Other"}, [(f"{LIB}.Parse", "cmd/a/main.go", 4)])
    assert any("path target differs" in f.reason for f in ck.check_structure(other_target, MAIN_PKG, TARGET))


def test_generic_instance_ends_at_generic_target():
    t = {"package": LIB, "symbol": "ParseAny[T]"}
    p = path(MAIN_PKG, t, [(f"{LIB}.ParseAny[string]", "cmd/a/main.go", 4)])
    assert ck.check_structure(p, MAIN_PKG, t) == []


def test_zero_edge_path_only_when_entry_is_target():
    t = {"package": MAIN_PKG, "symbol": "main"}
    assert ck.check_structure(path(MAIN_PKG, t, []), MAIN_PKG, t) == []
    assert ck.check_structure(path(MAIN_PKG, TARGET, []), MAIN_PKG, TARGET)


DECLS = [{"symbol": "main", "start": 3, "end": 9}, {"symbol": "init", "start": 11, "end": 14},
         {"symbol": "worker.Run", "start": 16, "end": 18}]


def edge(caller, callee, file="cmd/a/main.go", line=4):
    return {"caller": caller, "callee": callee, "call_site": {"file": file, "line": line}, "kind": "STATIC"}


def test_site_in_caller_declaration():
    assert ck.check_site(edge("p.main", "q.F", line=4), 0, 20, DECLS) is None
    assert ck.check_site(edge("p.main$1", "q.F", line=8), 0, 20, DECLS) is None        # closure inside main
    assert ck.check_site(edge("p.worker.Run", "q.F", line=17), 0, 20, DECLS) is None
    assert ck.check_site(edge("p.init#1", "q.F", line=12), 0, 20, DECLS) is None       # user init function


def test_site_failures():
    assert ck.check_site(edge("p.main", "q.F", line=17), 0, 20, DECLS)                 # line in another function
    assert ck.check_site(edge("p.main", "q.F", line=21), 0, 20, DECLS)                 # past the end of the file
    assert ck.check_site(edge("p.main", "q.F", line=4), 0, None, None)                 # file not readable
    assert ck.check_site(edge("p.main", "q.F", file="", line=0), 0, 20, DECLS)          # no site, not synthetic
    assert ck.check_site(edge("p.main", "q.F", file="x.go", line=0), 0, 20, DECLS)      # incomplete site


def test_package_initializer_outside_functions():
    assert ck.check_site(edge("p.init", "q.F", line=1), 0, 20, DECLS) is None           # package-level var initializer
    assert ck.check_site(edge("p.init", "q.F", line=4), 0, 20, DECLS)                   # but not inside main


def test_synthetic_edges_without_a_call_site():
    assert ck.check_site(edge("a.init", "b.init", "", 0), 0, None, None) is None
    assert ck.check_site(edge("b.init", "b.init#1", "", 0), 0, None, None) is None
    assert ck.check_site(edge("v.Impl.Run$bound", "v.Impl.Run", "", 0), 0, None, None) is None
    assert ck.check_site(edge("v.Impl.Run$thunk", "v.Impl.Run", "", 0), 0, None, None) is None
    assert ck.check_site(edge("v.Run$wrapper", "v.Run", "", 0), 0, None, None) is None
    assert ck.check_site(edge("v.Impl.Run$bound", "v.Other", "", 0), 0, None, None)      # forwards elsewhere
    # a method promoted through an embedded field (observed on D1: quic-go, antlr4-go)
    assert ck.check_site(edge("q.stream.Write$wrapper", "q.sendStream.Write", "", 0), 0, None, None) is None
    assert ck.check_site(edge("a/v4.FqlParser.Notify$wrapper", "b/v4.BaseParser.Notify", "", 0), 0, None, None) is None
    assert ck.check_site(edge("q.stream.Write$wrapper", "q.sendStream.Close", "", 0), 0, None, None)
    assert ck.check_site(edge("a.init", "b.Parse", "", 0), 0, None, None)               # init calling a function


def test_declares():
    assert ck.declares([{"symbol": "T.M", "start": 1, "end": 2}], "(*T).M")
    assert ck.declares([{"symbol": "ParseAny", "start": 1, "end": 2}], "ParseAny[T]")
    assert not ck.declares([{"symbol": "M", "start": 1, "end": 2}], "T.M")
