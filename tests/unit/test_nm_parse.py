from vulntrace.methods.linker import parse_nm

SAMPLE = """\
  46c500 T runtime.vdsoParseSymbols
  49c2e0 T vtfixtures/vulnlib.Parse
  49c420 t vtfixtures/vulnlib.(*PImpl).Run
  4cf758 R vtfixtures/vulnlib..dict.ParseAny[string]
         U some/undefined.Symbol
  58a0c0 B runtime.bss
  49c430 T vtfixtures/vulnlib.ParseAny[go.shape.string]

not a symbol line
"""


def test_parse_nm_extracts_type_and_name():
    syms = parse_nm(SAMPLE)
    assert ("T", "vtfixtures/vulnlib.Parse") in syms
    assert ("t", "vtfixtures/vulnlib.(*PImpl).Run") in syms
    assert ("R", "vtfixtures/vulnlib..dict.ParseAny[string]") in syms
    assert ("B", "runtime.bss") in syms


def test_parse_nm_handles_undefined_without_address():
    assert ("U", "some/undefined.Symbol") in parse_nm(SAMPLE)


def test_parse_nm_ignores_garbage_and_blank_lines():
    names = [n for _, n in parse_nm(SAMPLE)]
    assert "not a symbol line" not in names
    assert len(names) == 7


def test_parse_nm_empty():
    assert parse_nm("") == []
