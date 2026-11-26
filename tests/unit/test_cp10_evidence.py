"""CP10 deliverable 2: evidence honesty (fake runners and a fake verifier world, no Go).

The shown route is the best verified path (passes the CP9 filter, then fewer DYNAMIC steps, then
shorter); DYNAMIC steps carry `confirmed: false` and their kind; the verdict records the path
evidence level; nothing but labels changes; a ranked path that fails the verifier is never shown
and never changes a result."""

import copy
from pathlib import Path

import pytest

from tests.unit.cp7_support import (GOOD_PATH, LIB, MAIN_PKG, TARGET, FakeMethod, good_ctx, runners, vta_result)
from vulntrace.pipeline import evidence as ev
from vulntrace.pipeline import triage
from vulntrace.schemas import validation_errors
from vulntrace.verdict import NOT_REACHABLE, REACHABLE


def kinded(path, kind, dyn=None):
    p = copy.deepcopy(path)
    for e in p["edges"]:
        e["kind"] = kind
        if dyn:
            e["dynamic_kind"] = dyn
    return p


DYN = kinded(GOOD_PATH, "DYNAMIC", "INTERFACE_METHOD")
STATIC = kinded(GOOD_PATH, "STATIC")


class FeasVTA:
    """A PATH_FOUND VTA result with a CP9/CP10 feasibility answer."""

    def __init__(self, method_paths, evidence_path, ranked_path=None, status="FEASIBLE"):
        self.method_paths, self.evidence_path, self.ranked_path, self.status = method_paths, evidence_path, ranked_path, status

    def __call__(self, module_dir, main, targets):
        out = []
        for t in targets:
            r = vta_result(t, main, "PATH_FOUND", paths=copy.deepcopy(self.method_paths))
            f = {"status": self.status, "max_examined_paths": 20, "examined": [{"length": 1, "first_infeasible": None,
                                                                                   "dynamic_steps": 1}],
                 "examined_truncated": False, "evidence_path": copy.deepcopy(self.evidence_path),
                 "evidence_source": "EXAMINED_PATH" if self.status == "FEASIBLE" else None, "undecided_reason": None}
            if self.ranked_path is not None:
                f.update(rank_rule="FILTER_PASS_THEN_FEWEST_DYNAMIC_THEN_SHORTEST",
                         ranked_path=copy.deepcopy(self.ranked_path), ranked_index=0)
            r["details"]["feasibility"] = f
            out.append(r)
        return out


def run(vta, linker=None, evidence=True, verify=True):
    linker = linker or FakeMethod("linker", default=("PRESENT", {}))
    rn = runners(vta, linker, verifier_ctx=(lambda info, inc: good_ctx()) if verify else None)
    rn.feasibility, rn.evidence = {"max_examined_paths": 20, "rank_evidence": True}, evidence
    req = triage.TriageRequest(case_id="t", app=Path("/fake/app"), mode="targets", targets=[TARGET],
                               mains=[MAIN_PKG], run_verifier=verify)
    v = triage.run_triage(req, rn)
    assert validation_errors("verdict", v) == [], validation_errors("verdict", v)
    return v


def test_label_path_marks_dynamic_steps_unconfirmed():
    p = ev.label_path(kinded(GOOD_PATH, "DYNAMIC"))
    assert p["edges"][0]["confirmed"] is False and p["edges"][0]["dynamic_kind"] == ev.UNKNOWN_KIND
    s = ev.label_path(STATIC)
    assert "confirmed" not in s["edges"][0] and "dynamic_kind" not in s["edges"][0]


def test_shown_route_prefers_the_ranked_static_path():
    v = run(FeasVTA([DYN], DYN, ranked_path=STATIC))
    e = v["per_symbol"][0]
    assert e["result"] == REACHABLE and e["verified_path"] == DYN            # CP9 meaning unchanged
    assert e["shown_path"] == STATIC and e["path_evidence"]["source"] == ev.SRC_RANKED
    assert e["path_evidence"]["evidence_level"] == ev.STATIC_PATH and e["path_evidence"]["dynamic_steps"] == 0
    assert v["path_evidence"]["evidence_level"] == ev.STATIC_PATH
    assert v["path_evidence"]["statement"] == ev.ROUTE_STATEMENT
    assert ev.ROUTE_STATEMENT in v["limitations"]


def test_dynamic_route_is_labelled_with_its_count_and_kind():
    v = run(FeasVTA([DYN], DYN, ranked_path=DYN))
    e = v["per_symbol"][0]
    assert e["shown_path"]["edges"][0]["confirmed"] is False
    assert e["shown_path"]["edges"][0]["dynamic_kind"] == "INTERFACE_METHOD"
    assert v["path_evidence"]["evidence_level"] == ev.HAS_DYNAMIC_STEPS and v["path_evidence"]["dynamic_steps"] == 1
    assert v["path_evidence"]["dynamic_kinds"] == {"INTERFACE_METHOD": 1}


def test_ranked_path_failing_the_verifier_is_not_shown_and_changes_nothing():
    bad = copy.deepcopy(STATIC)
    bad["edges"][0]["call_site"]["line"] = 99                                 # no such call site
    v = run(FeasVTA([DYN], DYN, ranked_path=bad))
    e = v["per_symbol"][0]
    assert v["verdict"] == REACHABLE and e["result"] == REACHABLE and v["verification"]["status"] == "PASSED"
    assert e["path_checks"]["ranked_path_passed"] is False
    assert e["shown_path"]["edges"][0]["call_site"]["line"] == DYN["edges"][0]["call_site"]["line"]
    assert e["path_evidence"]["source"] == ev.SRC_FILTER_EVIDENCE
    assert v["verification"]["display_checks_by_kind"]  # counted apart
    assert v["verification"]["checks_by_kind"] == run(FeasVTA([DYN], DYN), evidence=False)["verification"]["checks_by_kind"]


def test_filter_passing_path_beats_a_shorter_unknown_one():
    long_static = copy.deepcopy(STATIC)
    cands = [(DYN, ev.SRC_METHOD, False, 2), (long_static, ev.SRC_FILTER_EVIDENCE, True, 1)]
    assert min(cands, key=ev.rank_key)[1] == ev.SRC_FILTER_EVIDENCE
    cands = [(DYN, ev.SRC_METHOD, False, 2), (STATIC, ev.SRC_METHOD, False, 3)]
    assert min(cands, key=ev.rank_key)[0] is STATIC                           # then fewer dynamic steps


def test_not_reachable_has_no_route():
    v = run(FakeMethod("vta", default=("NO_PATH", {})), FakeMethod("linker", default=("ABSENT", {})))
    assert v["verdict"] == NOT_REACHABLE
    assert v["path_evidence"]["evidence_level"] == ev.NO_ROUTE_SHOWN
    assert "shown_path" not in v["per_symbol"][0]


def test_without_the_verifier_nothing_is_shown():
    v = run(FeasVTA([DYN], DYN, ranked_path=STATIC), verify=False)
    assert v["verdict"] == REACHABLE and "shown_path" not in v["per_symbol"][0]
    assert v["path_evidence"]["evidence_level"] == ev.NO_ROUTE_SHOWN


def test_evidence_stage_adds_labels_only():
    with_ev = run(FeasVTA([DYN], DYN, ranked_path=STATIC))
    without = run(FeasVTA([DYN], DYN, ranked_path=STATIC), evidence=False)
    for v in (with_ev, without):
        v["timing"] = {}
        v["provenance"]["created_at"] = "x"
    stripped = ev.strip_cp10_evidence(with_ev)
    stripped["limitations"] = [x for x in stripped["limitations"] if x != ev.ROUTE_STATEMENT]
    assert stripped == ev.strip_cp10_evidence(without)
    with pytest.raises(AssertionError):
        bad = copy.deepcopy(with_ev)
        bad["verdict"] = NOT_REACHABLE
        ev.assert_labels_only(with_ev, bad)


def test_text_summary_states_the_route_caveat():
    v = run(FeasVTA([DYN], DYN, ranked_path=DYN))
    text = ev.text_summary(v)
    assert "REACHABLE" in text and "unconfirmed" in text and ev.ROUTE_STATEMENT in text
    assert f"{LIB}.Parse" in text and "INTERFACE_METHOD" in text
    nr = run(FakeMethod("vta", default=("NO_PATH", {})), FakeMethod("linker", default=("ABSENT", {})))
    assert ev.ROUTE_STATEMENT in ev.text_summary(nr)


def test_cli_legacy_targets_and_format_flags():
    import argparse

    from vulntrace.pipeline import cli
    from vulntrace.pipeline import symbols as sy

    p = argparse.ArgumentParser()
    cli.add_parser(p.add_subparsers(dest="cmd"))
    args = p.parse_args(["triage", "--advisory-file", "x.json", "--app", ".", "--legacy-targets", "--format", "text"])
    assert args.legacy_targets is True and args.format == "text"
    args = p.parse_args(["triage", "--advisory-file", "x.json", "--app", "."])
    assert args.legacy_targets is False and args.format == "json"
    assert cli.feasibility_settings(args, rank_evidence=True) == {"max_examined_paths": 20, "rank_evidence": True}
    assert cli.feasibility_settings(args) == {"max_examined_paths": 20}
    assert sy.POLICY_LEGACY != sy.POLICY_HYGIENE


def test_runners_request_ranking_and_labels_only_with_evidence():
    from vulntrace.methods.callgraph import build_request
    from vulntrace.pipeline.cli import default_runners

    r = default_runners(binary=Path("/nonexistent"), feasibility={"max_examined_paths": 20}, evidence=True)
    assert r.feasibility == {"max_examined_paths": 20, "rank_evidence": True} and r.evidence is True
    assert r.vta.keywords.get("label_dynamic") is True
    r0 = default_runners(binary=Path("/nonexistent"), feasibility={"max_examined_paths": 20})
    assert r0.feasibility == {"max_examined_paths": 20} and "label_dynamic" not in r0.vta.keywords
    req = build_request("reach", Path("."), "m", [TARGET])
    assert "label_dynamic" not in req and "feasibility" not in req
    assert build_request("reach", Path("."), "m", [TARGET], label_dynamic=True)["label_dynamic"] is True


def test_demo_page_says_the_route_caveat_and_labels_unconfirmed_steps():
    from vulntrace.demo import page

    assert page.ROUTE_STATEMENT == ev.ROUTE_STATEMENT
    v = run(FeasVTA([DYN], DYN, ranked_path=DYN))
    html = page.build_page([("t.json", v)])
    assert html.count(page.esc(ev.ROUTE_STATEMENT)) >= 3        # page intro, verdict note, the route itself
    assert "Route shown (an example from the call graph)" in html
    assert "DYNAMIC INTERFACE_METHOD, unconfirmed" in html and "HAS_DYNAMIC_STEPS" in html
    old = run(FakeMethod("vta", default=("NO_PATH", {})), FakeMethod("linker", default=("ABSENT", {})), evidence=False)
    assert page.esc(ev.ROUTE_STATEMENT) in page.build_page([("old.json", old)])   # also for pre-CP10 verdict files
