"""CP7b deliverables 4-5: adjudication sheets (nothing invented, untrusted text escaped), scoring a
filled sheet, and the results renderer (headline fixed before results). No Go, git or network."""

import copy
import json
import re
from pathlib import Path

import pytest

from vulntrace.__main__ import main
from vulntrace.d3 import report as rp
from vulntrace.d3 import score as sc
from vulntrace.d3 import sheet as sh

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "tests" / "contract" / "verdicts_cp7"
APP = "github.com/example/app"
EVIL = '<script>x</script> [click](https://evil.example) ![i](https://evil.example/i.png) `tick` **b**'


def _v(name):
    return json.loads((RECORDED / name).read_text(encoding="utf-8"))


def _row(cid, verdict, reasons=(), gv=None, app=APP):
    r = {"id": cid, "advisory": "GO-TEST-1", "app_repo": app, "app_tag": "v1.0.0", "app_commit": "c" * 40,
         "module": "example.com/lib", "version_selected": "v1.0.0", "created": "2026-01-01", "verdict": verdict,
         "reason_codes": list(reasons), "mode": "FIX", "evidence_level": "CHANGED_FUNCTION_LEVEL", "symbols": 1,
         "entries": {verdict: 1}, "verification": {"status": "PASSED"}, "case_seconds": 10.0,
         "helper_go_version": "go1.26.10"}
    if gv:
        r["govulncheck"] = {"verdict": gv[0], "level": gv[1], "agreement": gv[2], "trace": None}
    return r


# --- the sample ------------------------------------------------------------------------------------
def test_sample_rule_all_reachable_and_at_most_five_others():
    rows = ([_row(f"r{i}", "REACHABLE") for i in range(7)] + [_row(f"n{i}", "NOT_REACHABLE") for i in range(3)]
            + [_row(f"c{i}", "CANT_DETERMINE") for i in range(9)] + [_row("x", None)])
    s = sh.sample(rows)
    assert {f"r{i}" for i in range(7)} <= set(s)
    assert {f"n{i}" for i in range(3)} <= set(s)
    cds = [k for k in s if k.startswith("c")]
    assert len(cds) == 5 and "x" not in s
    assert cds == sorted(cds, key=sh._seeded)                                  # seeded order, reproducible
    assert sh.sample(list(reversed(rows))) == s


# --- Markdown safety -------------------------------------------------------------------------------
def test_md_escape_blocks_links_images_html_and_emphasis():
    out = sh.md(EVIL)
    assert "<script" not in out and "](" not in out and "![" not in out and "**" not in out
    assert sh.code_span("a``b").startswith("```") and sh.code_span("`x`") == "`` `x` ``"
    block = sh.code_block("x := `raw ``` inside`")
    assert block.startswith("````go\n") and block.endswith("\n````")


# --- links and source lines ------------------------------------------------------------------------
@pytest.mark.parametrize("file,expected", [
    ("cmd/a/main.go", f"https://{APP}/blob/{'c' * 40}/cmd/a/main.go#L7"),
    ("$GOMODCACHE/github.com/!burnt!sushi/toml@v1.2.0/decode.go", "https://github.com/BurntSushi/toml/blob/v1.2.0/decode.go#L7"),
    ("$GOMODCACHE/github.com/o/r/sub@v0.3.0/x.go", "https://github.com/o/r/blob/sub/v0.3.0/sub/x.go#L7"),
    ("$GOMODCACHE/github.com/o/r@v0.0.0-20200101000000-abcdefabcdef/x.go", "https://github.com/o/r/blob/abcdefabcdef/x.go#L7"),
    ("$GOMODCACHE/golang.org/x/net@v0.30.0/html/parse.go", "https://cs.opensource.google/go/x/net/+/v0.30.0:html/parse.go;l=7"),
    ("$GOROOT/src/net/http/server.go", "https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L7"),
    ("$GOMODCACHE/gopkg.in/yaml.v3@v3.0.1/decode.go", None),
    ("<local>/x.go", None)])
def test_source_link(file, expected):
    assert sh.source_link(file, 7, APP, "c" * 40, "go1.26.10") == expected


def test_read_lines_marks_the_line_and_stays_inside_its_root(tmp_path):
    (tmp_path / "app" / "cmd").mkdir(parents=True)
    (tmp_path / "app" / "cmd" / "m.go").write_text("package main\nfunc main() {\n\tlib.Parse()\n}\n", encoding="utf-8")
    roots = {"app": tmp_path / "app", "$GOMODCACHE": tmp_path / "mc", "$GOROOT": None}
    assert sh.read_lines("cmd/m.go", 3, roots) == "2  func main() {\n3> \tlib.Parse()\n4  }"
    assert sh.read_lines("cmd/m.go", 99, roots) is None
    assert sh.read_lines("../../etc/passwd", 1, roots) is None
    assert sh.read_lines("$GOROOT/src/x.go", 1, roots) is None


# --- sheet content: copied, never invented ---------------------------------------------------------
def _case_section(row, v, reason="every REACHABLE case", roots=None):
    return sh.case_markdown(row, v, reason, roots or {}, "go1.26.10")


def test_reachable_section_copies_path_steps_and_fields():
    v = _v("reachable_mode1.json")
    row = _row("app__GO-TEST-1", "REACHABLE", gv=("REACHABLE", "SYMBOL", "AGREE"))
    text = _case_section(row, v)
    paths = sh.reachable_paths(v)
    assert paths
    for e in paths[0]["path"]["edges"]:
        assert f"{e['call_site']['file']}:{e['call_site']['line']}" in text
        assert e["caller"] in text and e["callee"] in text
    assert text.count("**REACHABLE**") == 1
    assert "| adjudication | |" in text and "| truth |" not in text            # truth only for NR/CD


def test_non_reachable_section_invents_no_verdict_word():
    v = _v("cd_method_disagreement.json")
    row = _row("app__GO-TEST-2", "CANT_DETERMINE", ["METHOD_DISAGREEMENT"])
    text = _case_section(row, v, "all 1 CANT_DETERMINE cases")
    assert "**CANT\\_DETERMINE**" in text and "**REACHABLE**" not in text and "**NOT\\_REACHABLE**" not in text
    assert "METHOD\\_DISAGREEMENT" in text and "| truth | |" in text
    # every table row of the method summary is a real entry of the verdict
    n_entries = sum(int(m) for m in re.findall(r"\| (\d+) \|$", text, re.MULTILINE))
    assert n_entries == len(v["per_symbol"])


def test_untrusted_advisory_and_code_are_escaped(tmp_path):
    v = copy.deepcopy(_v("reachable_mode1.json"))
    v["advisory"]["summary"] = EVIL
    e = next(e for e in v["per_symbol"] if e.get("verified_path"))
    cs = e["verified_path"]["edges"][0]["call_site"]
    (tmp_path / Path(cs["file"]).parent).mkdir(parents=True, exist_ok=True)
    (tmp_path / cs["file"]).write_text("\n".join(["// ```` fence breaker"] * (cs["line"] + 2)), encoding="utf-8")
    text = _case_section(_row("a", "REACHABLE"), v, roots={"app": tmp_path})
    assert "<script" not in text and "](https://evil" not in text and "![" not in text
    assert "`````go" in text                                                 # fence longer than the code's backticks


def test_sheet_json_has_blank_fields_and_the_rule():
    rows = [_row("a", "REACHABLE"), _row("b", "NOT_REACHABLE"), _row("c", "CANT_DETERMINE", ["APP_LOAD_FAILED"])]
    j = sh.sheet_json(rows, sh.sample(rows))
    assert j["sample_rule"] == sh.SAMPLE_RULE and j["allowed_adjudications"] == list(sh.ADJUDICATIONS)
    for c in j["cases"]:
        assert c["adjudication"] is None and c["by"] is None and c["note"] is None and c["adjudicate"] is True
    assert "truth" not in j["cases"][0] and j["cases"][1]["truth"] is None


# --- scoring a filled sheet ------------------------------------------------------------------------
def _triage_doc(rows):
    return {"rows": rows, "summary": {"modes": {"FIX": len(rows)}, "pre_policy_verdicts": {},
                                      "govulncheck": {"disagreements": [{"id": r["id"], "ours": r["verdict"],
                                                                         "govulncheck": r["govulncheck"]["verdict"],
                                                                         "level": r["govulncheck"]["level"]}
                                                                        for r in rows if (r.get("govulncheck") or {}).get("agreement") == "DISAGREE"],
                                                      "not_affected": []},
                                      "seconds_per_case": {"p50": 1, "p95": 2, "max": 3, "total": 6},
                                      "toolchain": {"helper": ["go1.26.10"], "linker": ["go1.26.10"]}},
            "govulncheck": {"version": "v1.9.0", "mode": "source", "db": "pinned"}, "env": {}, "environment": {}}


ROWS = [_row("r1", "REACHABLE", gv=("REACHABLE", "SYMBOL", "AGREE")),
        _row("r2", "REACHABLE", gv=("NOT_REACHABLE", "PACKAGE", "DISAGREE")),
        _row("r3", "REACHABLE", app="github.com/other/app"),
        _row("n1", "NOT_REACHABLE", gv=("NOT_REACHABLE", "MODULE", "AGREE")),
        _row("c1", "CANT_DETERMINE", ["METHOD_DISAGREEMENT"])]


def _filled(**over):
    j = sh.sheet_json(ROWS, sh.sample(ROWS))
    answers = {"r1": "CORRECT", "r2": "INFEASIBLE_PATH", "r3": "WRONG", "n1": "WRONG", "c1": "CORRECT"}
    answers.update(over)
    for c in j["cases"]:
        c["adjudication"], c["by"], c["note"] = answers[c["id"]], "owner", "read the code"
    return j


def test_validate_catches_every_kind_of_problem():
    doc = _triage_doc(ROWS)
    assert sc.validate(_filled(), doc) == []
    bad = _filled(r1="MAYBE")
    bad["cases"][1]["verdict"] = "NOT_REACHABLE"
    bad["cases"][2]["adjudication"] = None
    bad["cases"][3]["by"] = ""
    bad["cases"][4]["truth"] = "SURE"
    bad["cases"].append(copy.deepcopy(bad["cases"][0]))
    errs = " | ".join(sc.validate(bad, doc))
    for needle in ("not one of", "differs from the triage result", "in the sample but not adjudicated", "without `by`",
                   "truth 'SURE'", "listed twice"):
        assert needle in errs
    nr_infeasible = _filled(n1="INFEASIBLE_PATH")
    assert any("REACHABLE verdicts only" in e for e in sc.validate(nr_infeasible, doc))
    with pytest.raises(sc.SheetError):
        sc.score(bad, doc)


def test_score_from_a_filled_sheet():
    s = sc.score(_filled(), _triage_doc(ROWS))
    assert s["verdicts"] == {"REACHABLE": 3, "NOT_REACHABLE": 1, "CANT_DETERMINE": 1} and s["answered"] == 4
    assert s["false_not_reachable"]["found"] == 1 and s["false_not_reachable"]["ids"] == ["n1"]
    p = s["reachable"]["precision"]
    assert (p["k"], p["n"]) == (1, 3) and 0 < p["ci_low"] < p["rate"] < p["ci_high"] < 1
    assert (s["reachable"]["path_exists_rate"]["k"], s["reachable"]["path_exists_rate"]["n"]) == (2, 3)
    assert s["cant_determine"]["share"]["k"] == 1 and s["cant_determine"]["reasons"] == {"METHOD_DISAGREEMENT": 1}
    assert s["govulncheck"]["agree_rate"]["k"] == 2 and s["govulncheck"]["agree_rate"]["n"] == 3
    assert s["govulncheck"]["disagreements_adjudicated"] == [{"id": "r2", "ours": "REACHABLE", "govulncheck": "NOT_REACHABLE",
                                                              "adjudication": "INFEASIBLE_PATH", "truth": None}]
    assert s["apps"] == 2 and s["per_app"]["github.com/other/app"] == {"REACHABLE": 1, "REACHABLE:WRONG": 1}
    cj = sc.score(_filled(r1="CANNOT_JUDGE", r2="CANNOT_JUDGE", r3="CANNOT_JUDGE"), _triage_doc(ROWS))
    assert cj["reachable"]["precision"]["n"] == 0 and cj["reachable"]["cannot_judge"] == 3


def test_examples_follow_the_fixed_rule():
    assert sc.pick_examples(_filled(), _triage_doc(ROWS)) == {"reachable": "r1", "cant_determine": "c1", "disagreement": "r2"}


# --- the renderer ----------------------------------------------------------------------------------
def test_headline_text_is_the_one_fixed_before_results():
    assert rp.HEADLINE == (
        "On {apps} real Go applications ({cases} application-advisory cases), VulnTrace answered {answered} cases and "
        "abstained (CANT_DETERMINE) on {cd}; adjudication judged {r_correct} of {r_decided} REACHABLE paths correct "
        "(precision {r_prec}, 95% Wilson interval {r_lo} to {r_hi}) and found {fnr} false NOT_REACHABLE among "
        "{nr_adj} adjudicated NOT_REACHABLE verdicts.")
    s = sc.score(_filled(), _triage_doc(ROWS))
    assert rp.headline(s).startswith("On 2 real Go applications (5 application-advisory cases), VulnTrace answered 4 cases")
    assert "no REACHABLE path could be judged" in rp.headline(
        sc.score(_filled(r1="CANNOT_JUDGE", r2="CANNOT_JUDGE", r3="CANNOT_JUDGE"), _triage_doc(ROWS)))


def test_render_puts_false_not_reachable_first_and_escapes():
    rows = copy.deepcopy(ROWS)
    sheet = _filled()
    sheet["cases"][0]["note"] = EVIL
    sel = {"rules": "docs/evaluation/D3_SELECTION_RULES.md", "toolchain": "go1.26.10", "vulndb_commit": "e" * 40,
           "status_counts": {"KEPT": 2, "TOO_LARGE": 3}, "diversity_note": "2 applications",
           "candidates": [{"order": 1, "repo": APP, "status": "KEPT", "rule": "A1-A11", "detail": "ok"}]}
    text = rp.render(sel, {}, _triage_doc(rows), sheet, {"r1": _v("reachable_mode1.json")})
    assert text.index("## False NOT_REACHABLE") < text.index("## Verdicts") < text.index("## REACHABLE precision")
    assert "<script" not in text and "](https://evil" not in text
    assert "### A REACHABLE case" in text and "### A disagreement with govulncheck" in text
    for lim in rp.FIXED_LIMITATIONS:
        assert lim in text


def test_cli_report_refuses_an_unfilled_sheet(tmp_path):
    rows = ROWS
    (tmp_path / "adjudication").mkdir()
    for name, obj in (("d3_selection.json", {"candidates": []}), ("d3_cases.json", {}), ("d3_triage.json", _triage_doc(rows))):
        (tmp_path / name).write_text(json.dumps(obj), encoding="utf-8")
    (tmp_path / "adjudication" / "adjudication.json").write_text(json.dumps(sh.sheet_json(rows, sh.sample(rows))), encoding="utf-8")
    out = tmp_path / "doc.md"
    assert main(["d3", "report", "--results", str(tmp_path), "--out", str(out)]) == 2 and not out.exists()
    (tmp_path / "adjudication" / "adjudication.json").write_text(json.dumps(_filled()), encoding="utf-8")
    assert main(["d3", "report", "--results", str(tmp_path), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# " + rp.TITLE)


def test_synthetic_edge_without_call_site_is_labelled_not_located():
    v = copy.deepcopy(_v("reachable_mode1.json"))
    e = next(e for e in v["per_symbol"] if e.get("verified_path"))
    e["verified_path"]["edges"][0]["call_site"] = {"file": "", "line": 0}
    text = _case_section(_row("a", "REACHABLE"), v)
    assert "synthetic edge, no call site" in text and "`:0`" not in text
    from vulntrace.demo import page
    html_text = page.build_page([("x", v)])
    assert "synthetic edge, no call site" in html_text and ">:0<" not in html_text


def test_summary_from_vulndb_is_copied_escaped_when_the_verdict_has_none():
    v = copy.deepcopy(_v("cd_method_disagreement.json"))
    v["advisory"].pop("summary", None)
    text = sh.case_markdown(_row("a", "CANT_DETERMINE"), v, None, {}, None, summary=EVIL)
    assert "\\[click\\]" in text and "<script" not in text


def test_context_only_targets_are_flagged_and_listed_after_changed_ones():
    v = copy.deepcopy(_v("reachable_mode1.json"))
    e = next(e for e in v["per_symbol"] if e.get("verified_path"))
    key = (e["target"]["package"], e["target"]["symbol"])
    for s_ in v["symbols"]:
        if (s_["package"], s_["symbol"]) == key:
            s_["context_only"] = True
    assert sh.only_context_reachable(v) is True
    text = _case_section(_row("a", "REACHABLE"), v)
    assert "(context only)" in text and "Target context only" in text and "True" in text
    other = copy.deepcopy(e)
    other["target"] = {"package": key[0], "symbol": "Changed"}
    v["per_symbol"].insert(0, other)
    v["symbols"].append({"package": key[0], "symbol": "Changed", "origin": "FIX_CHANGED", "context_only": False})
    paths = sh.reachable_paths(v)
    assert [p["context_only"] for p in paths] == [False, True] and sh.only_context_reachable(v) is False
