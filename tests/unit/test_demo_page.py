"""CP7b deliverable 6: the offline demo page escapes untrusted text and loads nothing external."""

import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from vulntrace.__main__ import main
from vulntrace.demo import page

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "tests" / "contract" / "verdicts_cp7"
EVIL = '<script>alert("x")</script><img src=x onerror=alert(1)>"\'&<a href="https://evil.example/">'


def _recorded() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RECORDED.glob("*.json")) if p.name != "index.json"]


def _hostile() -> dict:
    v = copy.deepcopy(json.loads((RECORDED / "reachable_mode1.json").read_text(encoding="utf-8")))
    v["case_id"] = EVIL
    v["advisory"]["summary"] = EVIL
    v["advisory"]["id"] = EVIL
    v["symbols"][0]["symbol"] = EVIL
    v["limitations"].append(EVIL)
    e = next(e for e in v["per_symbol"] if e.get("verified_path"))
    e["verified_path"]["edges"][0]["call_site"]["file"] = EVIL
    e["verified_path"]["edges"][0]["caller"] = EVIL
    e["target"]["symbol"] = EVIL
    return v


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attrs, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend((tag, k, v) for k, v in attrs)

    def handle_data(self, data):
        self.text.append(data)


def _parse(html_text: str) -> _Collector:
    c = _Collector()
    c.feed(html_text)
    return c


def test_untrusted_text_is_escaped_everywhere():
    out = page.build_page([("evil.json", _hostile())])
    c = _parse(out)
    assert "script" not in c.tags and "img" not in c.tags
    assert all(not k.startswith("on") for _, k, _ in c.attrs)              # no event handlers
    # the hostile text survives as visible text, escaped, not as markup
    assert EVIL in "".join(c.text)
    assert "&lt;script&gt;" in out and "<script" not in out


def test_page_loads_nothing_external_and_forbids_it():
    out = page.build_page([(f"{i}.json", v) for i, v in enumerate(_recorded())] + [("evil.json", _hostile())])
    c = _parse(out)
    assert not {"script", "link", "img", "iframe", "object", "embed", "form", "base"} & set(c.tags)
    hrefs = [v for t, k, v in c.attrs if k == "href"]
    assert hrefs and all(re.fullmatch(r"#v\d+-[0-9a-f]{10}", h) for h in hrefs)   # in-page anchors only
    assert not [v for t, k, v in c.attrs if k == "src"]
    csp = [v for t, k, v in c.attrs if t == "meta" and k == "content" and "default-src" in (v or "")]
    assert csp == [page.CSP] and "default-src 'none'" in page.CSP
    rest = out.replace(page.esc(EVIL), "")                                  # the only URL is in the escaped hostile text
    assert "http://" not in rest and "https://" not in rest
    assert "@import" not in out and "url(" not in out


def test_every_recorded_verdict_is_rendered_with_its_fields():
    vs = _recorded()
    out = page.build_page([(f"{i}.json", v) for i, v in enumerate(vs)])
    for v in vs:
        assert page.esc(v["case_id"]) in out
        for code in v["reason_codes"]:
            assert code in out
        for lim in v["limitations"]:
            assert page.esc(lim) in out
    reach = json.loads((RECORDED / "reachable_mode1.json").read_text(encoding="utf-8"))
    e = next(e for e in reach["per_symbol"] if e.get("verified_path"))
    for edge in e["verified_path"]["edges"]:
        cs = edge["call_site"]
        assert f"{page.esc(cs['file'])}:{cs['line']}" in out                 # file and line of every step
    m2 = json.loads((RECORDED / "reachable_mode2_candidate_level.json").read_text(encoding="utf-8"))
    assert "CANDIDATE_LEVEL" in page.build_page([("m2", m2)])
    assert "RANKED_CANDIDATE" in page.build_page([("m2", m2)])


def test_anchors_are_unique_and_text_free():
    vs = _recorded()
    ids = [page.anchor(v["case_id"], i) for i, v in enumerate(vs)]
    assert len(set(ids)) == len(ids)
    assert page.anchor(EVIL, 0).startswith("v0-") and "<" not in page.anchor(EVIL, 0)


def test_cli_builds_from_a_directory_and_rejects_non_verdicts(tmp_path, capsys):
    out = tmp_path / "demo.html"
    assert main(["demo", "build", "--dir", str(RECORDED), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "skipped" in capsys.readouterr().err                             # index.json is not a verdict
    bad = tmp_path / "bad.json"
    bad.write_text('{"x": 1}', encoding="utf-8")
    assert main(["demo", "build", "--verdict", str(bad), "--out", str(out)]) == 2
    assert main(["demo", "build", "--out", str(out)]) == 2
