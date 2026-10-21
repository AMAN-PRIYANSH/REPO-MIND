import pytest

from vulntrace.methods.linker import (
    UnsupportedSymbolForm,
    binary_name,
    escape_pkg_path,
    match_symbols,
    normalize_import_path,
    symbol_patterns,
)


def test_plain_function():
    assert symbol_patterns("ctrl/vulnlib", "Parse") == ["ctrl/vulnlib.Parse"]


def test_value_method_gives_value_and_pointer_forms():
    assert symbol_patterns("ctrl/vulnlib", "Impl.Run") == [
        "ctrl/vulnlib.Impl.Run",
        "ctrl/vulnlib.(*Impl).Run",
    ]


@pytest.mark.parametrize("sym", ["(*Impl).Run", "*Impl.Run", "Impl.Run"])
def test_pointer_method_spellings_equivalent(sym):
    assert symbol_patterns("p", sym) == ["p.Impl.Run", "p.(*Impl).Run"]


@pytest.mark.parametrize("sym,name", [("Map[T]", "Map"), ("List[K, V]", "List"), ("Parse[go.shape.int]", "Parse")])
def test_bare_generic_function_gives_a_prefix_pattern(sym, name):
    """CP3 task 0c: any instantiation's binary symbol is `pkg.Name[...]`, never the
    concrete type vulndb would name (observed by building generic_target with several
    instantiations), so the match is "any instantiation", encoded as a prefix pattern."""
    assert symbol_patterns("p", sym) == [f"p.{name}["]


@pytest.mark.parametrize("sym", ["Box[T].Get", "(*Box[T]).Get", "List[T].Push"])
def test_generic_methods_are_still_unsupported(sym):
    """A generic method, or a method on a generic type, embeds the type argument inside
    the receiver's own brackets (e.g. `pkg.(*List[go.shape.string]).Push`), not after the
    method name, so no reliable rule for this form was found."""
    with pytest.raises(UnsupportedSymbolForm):
        symbol_patterns("p", sym)


@pytest.mark.parametrize("sym", ["a.b.c", "", "1abc", "A-B"])
def test_unrecognised_symbol_forms_are_unsupported(sym):
    with pytest.raises(UnsupportedSymbolForm):
        symbol_patterns("p", sym)


def test_dot_in_last_path_element_is_escaped():
    assert escape_pkg_path("gopkg.in/yaml.v3") == "gopkg.in/yaml%2ev3"
    assert symbol_patterns("gopkg.in/yaml.v3", "Unmarshal") == ["gopkg.in/yaml%2ev3.Unmarshal"]


def test_major_version_path_unchanged():
    assert escape_pkg_path("github.com/x/y/v2") == "github.com/x/y/v2"


def test_windows_style_paths_are_normalised():
    assert normalize_import_path("vtfixtures\\cmd\\direct_call") == "vtfixtures/cmd/direct_call"
    assert symbol_patterns("ctrl\\vulnlib", "Parse") == ["ctrl/vulnlib.Parse"]


def test_windows_binary_gets_exe_suffix():
    assert binary_name("windows").endswith(".exe")
    assert not binary_name("linux").endswith(".exe")


def test_match_only_text_symbols():
    nm = [("T", "p.Parse"), ("R", "p.Other"), ("t", "p.Impl.Run"), ("D", "p.Var")]
    assert match_symbols(nm, ["p.Parse"]) == ["p.Parse"]
    assert match_symbols(nm, ["p.Impl.Run", "p.(*Impl).Run"]) == ["p.Impl.Run"]
    assert match_symbols(nm, ["p.Var"]) == []  # data symbol is not code
    assert match_symbols(nm, ["p.Absent"]) == []


def test_match_is_exact_not_prefix():
    assert match_symbols([("T", "p.ParseTiny")], ["p.Parse"]) == []


def test_generic_prefix_pattern_matches_any_shape():
    nm = [("T", "p.ParseAny[go.shape.string]"), ("T", "p.ParseAny[go.shape.int]"), ("R", "p.Other")]
    assert match_symbols(nm, symbol_patterns("p", "ParseAny[T]")) == [
        "p.ParseAny[go.shape.int]", "p.ParseAny[go.shape.string]"]


def test_generic_prefix_does_not_match_a_different_function_name():
    """`p.Parse[` must not match `p.ParseAny[...]`: the character after `Parse` is `A`, not `[`."""
    nm = [("T", "p.ParseAny[go.shape.string]")]
    assert match_symbols(nm, symbol_patterns("p", "Parse[T]")) == []
