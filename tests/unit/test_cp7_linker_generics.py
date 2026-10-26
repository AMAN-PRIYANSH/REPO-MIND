"""CP7: the linker method matches generic instantiations of targets written in vulndb form
(no type parameters). The names below were observed with Go 1.24.7 and -gcflags=all=-l
(a probe module with List[T].Push, Box[T].Get, Map[T, U]); tests/integration/test_cp7_triage.py
builds such a module and checks the real binary."""

import pytest

from vulntrace.methods.linker import is_generic_instance, match_generic_instances, run_linker_method

P = "probe.example/lib"
NM = [("T", f"{P}.(*List[go.shape.int]).Push"), ("T", f"{P}.(*List[go.shape.string]).Push"),
      ("R", f"{P}..dict.List[int]"), ("T", f"{P}.Box[go.shape.[]uint8].Get"),
      ("T", f"{P}.Map[go.shape.int,go.shape.string]"), ("T", f"{P}.Plain"),
      ("T", f"{P}.Map[go.shape.int,go.shape.string].func1"), ("T", f"{P}.Other.Push")]


@pytest.mark.parametrize("symbol,want", [
    ("Map", [f"{P}.Map[go.shape.int,go.shape.string]"]),
    ("List.Push", [f"{P}.(*List[go.shape.int]).Push", f"{P}.(*List[go.shape.string]).Push"]),
    ("(*List).Push", [f"{P}.(*List[go.shape.int]).Push", f"{P}.(*List[go.shape.string]).Push"]),
    ("Box.Get", [f"{P}.Box[go.shape.[]uint8].Get"]),
    ("Plain", []),            # not generic: the exact pattern handles it, never this rule
    ("Other.Push", []),       # a different type's method with the same name
    ("Ma", []),               # a prefix of another function's name
    ("List.Pus", []),
    ("Map[T]", []),           # bracketed forms keep CP3's prefix rule instead
])
def test_generic_instances(symbol, want):
    assert match_generic_instances(NM, P, symbol) == want


def test_closure_and_rodata_do_not_count():
    assert not is_generic_instance(f"{P}.Map[go.shape.int].func1", P, "Map")
    assert match_generic_instances([("R", f"{P}..dict.List[int]")], P, "List") == []


def test_nested_brackets_are_balanced():
    assert is_generic_instance(f"{P}.Box[go.shape.map[string]int].Get", P, "Box.Get")
    assert not is_generic_instance(f"{P}.Box[go.shape.int]].Get", P, "Box.Get")


def test_linker_method_uses_the_rule_only_when_exact_patterns_miss():
    nm_text = "\n".join(f"  4000 {t} {n}" for t, n in NM)

    def runner(cmd, **kw):
        class P_:
            returncode = 0
            stdout = {"version": "go version go1.24.7 linux/amd64", "env": "linux\namd64\n"}.get(cmd[1], nm_text)
            stderr = ""
        return P_()

    res = run_linker_method("/x", "probe.example/cmd/app", [{"package": P, "symbol": "Map"},
                                                           {"package": P, "symbol": "Plain"},
                                                           {"package": P, "symbol": "Missing"}], runner=runner)
    assert [r["result"] for r in res] == ["PRESENT", "PRESENT", "ABSENT"]
    assert res[0]["details"]["generic_instances"] is True and "generic_instances" not in res[1]["details"]
