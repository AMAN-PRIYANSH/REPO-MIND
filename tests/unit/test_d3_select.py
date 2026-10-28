"""CP7b deliverable 1: the D3 selection rules, without network, git or Go."""

import json
from pathlib import Path

import pytest

from vulntrace.d3 import select as sl

ROOT = Path(__file__).resolve().parents[2]


# --- V2/V3 range semantics --------------------------------------------------------------------------
@pytest.mark.parametrize("version,events,expected", [
    ("v1.2.3", [{"introduced": "1.0.0"}, {"fixed": "1.2.4"}], True),
    ("v1.2.4", [{"introduced": "1.0.0"}, {"fixed": "1.2.4"}], False),       # fixed is exclusive
    ("v0.9.0", [{"introduced": "1.0.0"}, {"fixed": "1.2.4"}], False),       # introduced is inclusive
    ("v1.0.0", [{"introduced": "1.0.0"}, {"fixed": "1.2.4"}], True),
    ("v0.1.0", [{"fixed": "0.2.0"}], True),                                  # starts with fixed: open from 0
    ("v1.5.0", [{"fixed": "1.2.0"}, {"introduced": "1.4.0"}, {"fixed": "1.5.1"}], True),
    ("v1.3.0", [{"fixed": "1.2.0"}, {"introduced": "1.4.0"}, {"fixed": "1.5.1"}], False),
    ("v2.0.0", [{"introduced": "0"}], True),                                 # no fix
    ("v3.1.0+incompatible", [{"fixed": "3.2.0"}], True),
    ("v0.0.0-20200101000000-abcdefabcdef", [{"fixed": "0.0.0-20210101000000-123456789abc"}], True),
    ("v1.22.0-rc.1", [{"introduced": "1.22.0-0"}, {"fixed": "1.22.2"}], True),
    ("v1.0.0", [], True),                                                    # no versions: all affected
])
def test_version_affected(version, events, expected):
    assert sl.version_affected(version, events) is expected


def test_version_affected_unparseable_is_none():
    assert sl.version_affected("master", [{"fixed": "1.0.0"}]) is None
    assert sl.version_affected("v1.0.0", [{"fixed": "not-a-version"}]) is None


# --- go.mod, tags, toolchain ------------------------------------------------------------------------
GO_MOD = """module github.com/acme/app

go 1.23.4

toolchain go1.24.1

require github.com/single/line v1.0.0 // indirect

require (
\tgithub.com/a/b v1.2.3
\tgithub.com/c/d v0.0.0-20200101000000-abcdefabcdef // indirect
\t"github.com/quoted/e" v2.0.0+incompatible
)

replace github.com/a/b => github.com/fork/b v1.2.4

replace (
\tgithub.com/c/d v0.0.0-20200101000000-abcdefabcdef => ../local/d
)

exclude github.com/x/y v1.0.0
"""


def test_parse_go_mod():
    gm = sl.parse_go_mod(GO_MOD)
    assert gm["module"] == "github.com/acme/app"
    assert gm["go"] == "1.23.4"
    assert gm["requires"] == {"github.com/single/line": "v1.0.0", "github.com/a/b": "v1.2.3",
                              "github.com/c/d": "v0.0.0-20200101000000-abcdefabcdef",
                              "github.com/quoted/e": "v2.0.0+incompatible"}
    assert gm["replaced"] == ["github.com/a/b", "github.com/c/d"]
    assert "github.com/x/y" not in gm["requires"]


@pytest.mark.parametrize("directive,toolchain,ok", [
    ("1.23.4", "go1.26.10", True), ("1.26", "go1.26.10", True), ("1.26.10", "go1.26.10", True),
    ("1.26.11", "go1.26.10", False), ("1.27", "go1.26.10", False), (None, "go1.26.10", True)])
def test_go_directive_ok(directive, toolchain, ok):
    assert sl.go_directive_ok(directive, toolchain) is ok


def test_parse_ls_remote_prefers_peeled_commit_and_stable_tag_order():
    text = ("aaa\trefs/tags/v1.2.0\nbbb\trefs/tags/v1.2.0^{}\nccc\trefs/tags/v1.10.0\nddd\trefs/tags/v1.10.1-rc.1\n"
            "eee\trefs/tags/api/v9.0.0\nfff\trefs/tags/1.11.0\nggg\trefs/heads/main\nhhh\trefs/tags/v1.9.9\n")
    refs = sl.parse_ls_remote(text)
    assert refs["v1.2.0"] == "bbb"
    assert "main" not in refs
    assert [t for t, _ in sl.stable_tags(refs)] == ["v1.10.0", "v1.9.9", "v1.2.0"]   # numeric, no rc/prefix


# --- ordering and case choice ----------------------------------------------------------------------
def test_candidate_order_is_seeded_not_file_order():
    cands = [{"repo": f"github.com/o{i}/r{i}", "domain": "d"} for i in range(10)]
    a = sl.candidate_order(cands, 20261028)
    assert a == sl.candidate_order(list(reversed(cands)), 20261028)          # independent of file order
    assert [c["repo"] for c in a] != [c["repo"] for c in cands] or len(cands) < 2
    assert a != sl.candidate_order(cands, 1)                                 # the seed matters


def _e(i, module):
    return {"id": f"GO-2026-{i:04d}", "module": module, "created": "2026-01-01", "fix_commit": {},
            "packages": [module], "core_symbols": 1, "version": "v1.0.0"}


def test_pick_cases_round_robin_over_modules_and_cap():
    elig = [_e(1, "m/a"), _e(2, "m/a"), _e(3, "m/a"), _e(4, "m/b"), _e(5, "m/c"), _e(6, "m/c")]
    picked = sl.pick_cases("github.com/o/app", elig, 7, 4)
    assert len(picked) == 4
    first_round = picked[:3]
    assert sorted(p["module"] for p in first_round) == ["m/a", "m/b", "m/c"]  # one per module first
    assert len({p["id"] for p in picked}) == 4
    assert picked == sl.pick_cases("github.com/o/app", list(reversed(elig)), 7, 4)   # deterministic


def test_pick_cases_counts_an_advisory_once():
    elig = [_e(1, "m/a"), {**_e(1, "m/b")}]
    assert [p["id"] for p in sl.pick_cases("x", elig, 7, 4)] == ["GO-2026-0001"]


def test_eligible_advisories_skips_replaced_and_out_of_range():
    index = {"m/a": [{"id": "GO-1", "module": "m/a", "events": [{"fixed": "1.5.0"}], "created": None,
                      "fix_commit": {}, "packages": ["m/a"], "core_symbols": 1}],
             "m/b": [{"id": "GO-2", "module": "m/b", "events": [{"fixed": "1.0.0"}], "created": None,
                      "fix_commit": {}, "packages": ["m/b"], "core_symbols": 1}],
             "m/c": [{"id": "GO-3", "module": "m/c", "events": [{"fixed": "9.0.0"}], "created": None,
                      "fix_commit": {}, "packages": ["m/c"], "core_symbols": 1}]}
    elig, bad = sl.eligible_advisories({"m/a": "v1.4.0", "m/b": "v1.0.0", "m/c": "v1.0.0"}, index, ["m/c"])
    assert [e["id"] for e in elig] == ["GO-1"]
    assert bad == []


# --- the rule pipeline with a fake probe -----------------------------------------------------------
class FakeProbe:
    """Per repo: tags {name: (sha, date)}, go.mod text, prepare error, mains, build errors, selected versions."""

    def __init__(self, repos):
        self.repos = repos
        self.calls = []

    def list_tags(self, repo):
        self.calls.append(("list_tags", repo))
        r = self.repos.get(repo)
        if r is None or r.get("unreachable"):
            return None, "fatal: repository not found"
        return {t: sha for t, (sha, _) in r["tags"].items()}, None

    def tag_commit(self, repo, tag):
        sha, date = self.repos[repo]["tags"][tag]
        return sha, date, None

    def file_at(self, repo, sha, path):
        return self.repos[repo].get("go_mod")

    def prepare(self, repo, sha):
        self.calls.append(("prepare", repo))
        return Path("/nonexistent"), self.repos[repo].get("prepare_error")

    def list_mains(self, module_dir):
        repo = self._last("prepare")
        return self.repos[repo].get("mains", []), [], None

    def build(self, module_dir, main):
        return self.repos[self._last("prepare")].get("build_errors", {}).get(main)

    def selected_versions(self, module_dir, paths):
        r = self.repos[self._last("prepare")]
        return {p: v for p, v in r.get("selected", {}).items() if p in paths}, None

    def _last(self, kind):
        return [c for c in self.calls if c[0] == kind][-1][1]


INDEX = {"github.com/vuln/lib": [{"id": "GO-2026-0001", "module": "github.com/vuln/lib",
                                  "events": [{"introduced": "1.0.0"}, {"fixed": "1.3.0"}], "created": "2026-02-01",
                                  "fix_commit": {"host": "github.com", "owner": "vuln", "repo": "lib", "sha": "f" * 40},
                                  "packages": ["github.com/vuln/lib"], "core_symbols": 2}]}

GOOD_MOD = "module github.com/{o}/{r}\n\ngo 1.22\n\nrequire github.com/vuln/lib v1.2.0\n"


def _repo(o, r, **kw):
    base = {"tags": {"v2.0.0": ("s2" + "0" * 38, "2026-03-01T00:00:00Z"), "v1.9.0": ("s1" + "0" * 38, "2025-11-30T10:00:00+02:00")},
            "go_mod": GOOD_MOD.format(o=o, r=r), "mains": [f"github.com/{o}/{r}/cmd/x"],
            "selected": {"github.com/vuln/lib": "v1.2.0"}}
    base.update(kw)
    return base


def _config(repos):
    return {"seed": 20261028, "pin_cutoff": "2025-12-31T23:59:59Z", "max_apps": 2, "max_cases_per_app": 4,
            "max_requires": 150, "max_mains": 10, "max_tag_probes": 60,
            "candidates": [{"repo": k, "domain": v.pop("_domain")} for k, v in repos.items()]}


def test_select_applies_rules_in_order_with_reasons():
    repos = {
        "github.com/ok1/app": {**_repo("ok1", "app"), "_domain": "d1"},
        "github.com/ok2/app": {**_repo("ok2", "app"), "_domain": "d2"},
        "github.com/gone/app": {"unreachable": True, "_domain": "d3"},
        "github.com/new/app": {**_repo("new", "app", tags={"v1.0.0": ("n" * 40, "2026-01-01T00:00:00Z")}), "_domain": "d4"},
        "github.com/gotoo/app": {**_repo("gotoo", "app", go_mod="module github.com/gotoo/app\ngo 1.99\n"), "_domain": "d5"},
        "github.com/safe/app": {**_repo("safe", "app", go_mod="module github.com/safe/app\ngo 1.22\nrequire github.com/vuln/lib v1.3.0\n"),
                                "_domain": "d6"},
        "github.com/many/app": {**_repo("many", "app", mains=[f"github.com/many/app/cmd/{i}" for i in range(11)]), "_domain": "d7"},
        "github.com/nobuild/app": {**_repo("nobuild", "app", build_errors={"github.com/nobuild/app/cmd/x": "cgo needed"}),
                                   "_domain": "d8"},
        "github.com/bumped/app": {**_repo("bumped", "app", selected={"github.com/vuln/lib": "v1.3.1"}), "_domain": "d9"},
        "github.com/sameown/other": {**_repo("sameown", "other"), "_domain": "d1"},
    }
    cfg = _config(repos)
    cfg["max_apps"] = 99
    probe = FakeProbe(repos)
    res = sl.select(cfg, INDEX, probe, "go1.26.10", log=lambda m: None)
    by = {r["repo"]: r for r in res["records"]}
    assert by["github.com/gone/app"]["status"] == sl.REPO_UNREACHABLE
    assert by["github.com/new/app"]["status"] == sl.NO_TAG_BEFORE_CUTOFF
    assert by["github.com/gotoo/app"]["status"] == sl.GO_TOO_NEW
    assert by["github.com/safe/app"]["status"] == sl.NO_ELIGIBLE_ADVISORY
    assert by["github.com/many/app"]["status"] == sl.TOO_MANY_MAINS
    assert by["github.com/nobuild/app"]["status"] == sl.BUILD_FAILED
    assert by["github.com/bumped/app"]["status"] == sl.NO_ELIGIBLE_ADVISORY_SELECTED
    kept = [r["repo"] for r in res["kept"]]
    assert "github.com/ok2/app" in kept
    # domain d1 is shared by ok1 and sameown: whichever comes second in seeded order is dropped by A1
    d1 = [r for r in res["records"] if r["domain"] == "d1"]
    assert sorted(r["status"] for r in d1) == sorted([sl.KEPT, sl.DIVERSITY_DOMAIN])
    for r in res["records"]:
        assert r["rule"] == sl.RULE_OF[r["status"]] and r["detail"]
    ok = by["github.com/ok2/app"]
    assert ok["pin"]["tag"] == "v1.9.0"                    # newest tag dated on or before the cutoff
    assert ok["cases"][0]["advisory"] == "GO-2026-0001"
    assert ok["cases"][0]["version_selected"] == "v1.2.0"
    # a candidate dropped by a cheap rule is never downloaded
    assert ("prepare", "github.com/safe/app") not in probe.calls
    assert ("prepare", "github.com/gotoo/app") not in probe.calls


def test_select_stops_at_quota_and_lists_the_rest():
    repos = {f"github.com/o{i}/app": {**_repo(f"o{i}", "app"), "_domain": f"d{i}"} for i in range(4)}
    cfg = _config(repos)
    res = sl.select(cfg, INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)
    statuses = [r["status"] for r in res["records"]]
    assert statuses == [sl.KEPT, sl.KEPT, sl.NOT_EVALUATED, sl.NOT_EVALUATED]
    assert sl.case_list(res["kept"])[0]["app_tag"] == "v1.9.0"
    assert "no two share" in sl.diversity_note(res["kept"])


def test_committed_candidate_file_matches_rules_doc():
    cfg = json.loads((ROOT / "docs" / "evaluation" / "d3_candidates.json").read_text(encoding="utf-8"))
    doc = (ROOT / "docs" / "evaluation" / "D3_SELECTION_RULES.md").read_text(encoding="utf-8")
    assert cfg["seed"] == 20261028 and '"20261028:" + repo' in doc
    assert cfg["pin_cutoff"] == "2025-12-31T23:59:59Z" and "2025-12-31T23:59:59Z" in doc
    assert cfg["max_requires"] == 150 and "At most 150" in doc
    assert cfg["max_mains"] == 10 and cfg["max_apps"] == 5 and cfg["max_cases_per_app"] == 4
    repos = [c["repo"] for c in cfg["candidates"]]
    assert len(repos) == len(set(repos))
    assert all(r.startswith("github.com/") and r.count("/") == 2 for r in repos)
