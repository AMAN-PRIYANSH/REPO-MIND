"""Synthetic advisories for the fixture suite (D2), so Mode 1 and Mode 2 run on fixtures through
the real evidence builders (CP7 deliverable 4).

A throw-away git repository holds a copy of `fixtures/reachability` (module `vtfixtures`) tagged
`v1.0.0`: that is the vulnerable version, byte for byte the committed fixtures, so each fixture
case's truth label (about its target symbol) carries over unchanged. For every distinct target
symbol S of the suite, a branch from `v1.0.0` gets two commits and a tag `v1.0.1-<slug>`:

1. a decoy commit that changes `vulnlib.Safe` (not vulnerable; called by some fixture mains);
2. the fix commit, which changes the body of S and nothing else.

Mode 1 uses the fix commit. Its FixEvidence candidates are S, plus, for the one-line functions
`ParseTiny`, `ParseAny` and `Safe`, any neighbour within git's 3 context lines (CP3 attributes a
hunk by its whole span; those neighbours are flagged `context_only`). The truth label is about S;
the results list every analysed symbol. Mode 2 uses the release range `v1.0.0..v1.0.1-<slug>`
(candidates: S and Safe). Because Safe is reachable
from some mains whose truth for S is NOT_REACHABLE, Mode 2 can say REACHABLE at candidate level
where the vulnerability is not reachable: that is the CANDIDATE_LEVEL caveat, measured on
purpose, not a defect of the fixtures. Nothing in `fixtures/` is changed.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from vulntrace.dataset import fix_evidence as fe_mod
from vulntrace.dataset import git_fetch, materialize, release_range as rr_mod
from vulntrace.paths import FIXTURES_DIR

MODULE = "vtfixtures"
HOST, OWNER = "local", "vtfixtures"
VULNERABLE = "1.0.0"
VULNLIB = Path("vulnlib") / "vulnlib.go"

DECOY = ('func Safe(s string) string { return strings.ToUpper(s) }',
         'func Safe(s string) string { return strings.ToUpper(strings.TrimSpace(s)) }')
DECOY_SUBJECT = "vulnlib: trim input in Safe"

# target symbol -> (slug, the fix as one exact replacement in vulnlib.go, fix commit subject)
FIXES: dict[str, tuple[str, tuple[str, str], str]] = {
    "Parse": ("parse", ("if s[i] == ' ' {", "if s[i] == ' ' || s[i] == '\\t' {"),
              "vulnlib: Parse also escapes tabs"),
    "ParseTiny": ("parsetiny", ('func ParseTiny(s string) string { return "tiny:" + s }',
                                'func ParseTiny(s string) string { return "tiny:" + strings.TrimSpace(s) }'),
                  "vulnlib: ParseTiny trims its input"),
    "ParseAny[T]": ("parseany", ('strings.Repeat("x", 1)', 'strings.Repeat("y", 1)'),
                    "vulnlib: ParseAny uses a fixed placeholder"),
    "Impl.Run": ("impl-run", ("func (Impl) Run(s string) string { return Parse(s) }",
                              "func (Impl) Run(s string) string { return Parse(strings.TrimSpace(s)) }"),
                 "vulnlib: Impl.Run trims its payload"),
    "PImpl.Run": ("pimpl-run", ("func (*PImpl) Run(s string) string { return Parse(s) }",
                                "func (*PImpl) Run(s string) string { return Parse(strings.TrimSpace(s)) }"),
                  "vulnlib: PImpl.Run trims its payload"),
}


class FixtureRepoError(Exception):
    pass


def _git(args: list[str], cwd: Path) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise FixtureRepoError(f"git {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout.strip()


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise FixtureRepoError(f"{path.name}: expected exactly one {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def _commit(src: Path, message: str) -> str:
    _git(["add", "-A"], src)
    _git(["-c", "user.email=fixtures@vulntrace.invalid", "-c", "user.name=vulntrace fixtures",
          "commit", "-q", "--no-gpg-sign", "-m", message], src)
    return _git(["rev-parse", "HEAD"], src)


def build_source_repo(work_dir: Path, fixtures_dir: Path = FIXTURES_DIR) -> tuple[Path, dict[str, dict[str, str]]]:
    """(repo dir, {target symbol: {slug, fix_sha, tag}}). The repository lives under `work_dir`."""
    src = Path(work_dir) / "vtfixtures-src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(fixtures_dir, src, ignore=shutil.ignore_patterns("manifest.json"))
    _git(["init", "-q", "-b", "main"], src)
    base = _commit(src, "vtfixtures v1.0.0 (the committed fixture suite)")
    _git(["tag", f"v{VULNERABLE}"], src)
    out = {}
    for symbol, (slug, (old, new), subject) in FIXES.items():
        _git(["checkout", "-q", "-B", f"fix-{slug}", base], src)
        _replace_once(src / VULNLIB, *DECOY)
        _commit(src, DECOY_SUBJECT)
        _replace_once(src / VULNLIB, old, new)
        sha = _commit(src, subject)
        tag = f"v{VULNERABLE}-{slug}-fixed"
        _git(["tag", tag], src)
        out[symbol] = {"slug": slug, "fix_sha": sha, "tag": tag}
    _git(["checkout", "-q", "main"], src)
    return src, out


def advisory_for(symbol: str, info: dict[str, str]) -> dict[str, Any]:
    """A VulnCase-like record (only fields triage reads, plus ids). The text is synthetic."""
    slug = info["slug"]
    return {"id": f"FIXTURE-{slug.upper()}", "summary": f"Improper input handling in vtfixtures/vulnlib {symbol}",
            "details": f"The {symbol} function of package vtfixtures/vulnlib mishandles untrusted input.",
            "module": MODULE, "vulnerable_at": VULNERABLE, "fixed_in": info["tag"][1:],
            "fix_commits": [{"host": HOST, "owner": OWNER, "repo": f"vtfixtures-{slug}", "sha": info["fix_sha"]}],
            "_source": "synthetic fixture advisory (CP7)"}


def build_pack(work_dir: Path, binary=None, fixtures_dir: Path = FIXTURES_DIR) -> dict[str, dict[str, Any]]:
    """{target symbol: {advisory, fix_evidence, release_range, candidate_code}} built with the CP3
    evidence code from the local repository (no network)."""
    src, infos = build_source_repo(work_dir, fixtures_dir)
    cache = Path(work_dir) / "git-cache"
    pack = {}
    for symbol, info in infos.items():
        adv = advisory_for(symbol, info)
        fc = adv["fix_commits"][0]
        fe = fe_mod.build_fix_evidence(adv["id"], adv["fix_commits"], binary=binary, cache_root=cache,
                                       remote_url=str(src))
        fe["status"] = "AVAILABLE" if fe.get("candidates") else "EMPTY"
        rr = rr_mod.build_release_range(adv["id"], MODULE, adv["vulnerable_at"], adv["fixed_in"], fc["host"],
                                        fc["owner"], fc["repo"], binary=binary, cache_root=cache, remote_url=str(src))
        code = materialize.extract_candidate_code(git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], cache), rr)
        pack[symbol] = {"advisory": adv, "fix_evidence": fe, "release_range": rr, "candidate_code": code}
    return pack


def pack_facts(pack: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What the evidence builders produced per advisory (recorded in the results)."""
    return {sym: {"id": p["advisory"]["id"], "fix_status": p["fix_evidence"].get("status"),
                  "fix_candidates": sorted(c["symbol"] for c in p["fix_evidence"].get("candidates", [])),
                  "range_status": p["release_range"].get("status"),
                  "range_candidates": sorted(c["symbol"] for c in p["release_range"].get("candidates", [])),
                  "range_commits": len(p["release_range"].get("commits", []))}
            for sym, p in sorted(pack.items())}
