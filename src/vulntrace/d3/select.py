"""`python -m vulntrace d3 select` (CP7b deliverable 1).

Applies the written rules of `docs/evaluation/D3_SELECTION_RULES.md` to the fixed candidate list
`docs/evaluation/d3_candidates.json`, in a seeded order, and prints for every candidate the rule
that kept or dropped it. The rules never look at a triage result; this module does not import the
pipeline.

Pure rule functions come first (tested without network); the `Probe` class does the explicit,
network-using steps: `git ls-remote`, blob-less tag fetches, `git archive` of the pinned commit,
`go mod download` from the public module proxy. Nothing from an application is executed: its main
packages are compiled to a temporary file that is deleted unread (CLAUDE.md section 8), with
`GOTOOLCHAIN=local` and `CGO_ENABLED=0`; go.mod and go.sum are never changed (`-mod=readonly`).
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vulntrace.dataset import datasets, git_fetch, vulndb
from vulntrace.dataset.govers import GoVersion, InvalidVersion, parse_version
from vulntrace.paths import REPO_ROOT

SCHEMA_VERSION = "1.0"
CANDIDATES_PATH = REPO_ROOT / "docs" / "evaluation" / "d3_candidates.json"
RULES_DOC = "docs/evaluation/D3_SELECTION_RULES.md"

# statuses (rule order of the rules document)
KEPT = "KEPT"
NOT_EVALUATED = "NOT_EVALUATED_QUOTA_FILLED"
DIVERSITY_OWNER, DIVERSITY_DOMAIN = "DIVERSITY_OWNER", "DIVERSITY_DOMAIN"
REPO_UNREACHABLE = "REPO_UNREACHABLE"
NO_TAG_BEFORE_CUTOFF = "NO_TAG_BEFORE_CUTOFF"
NO_ROOT_GO_MOD = "NO_ROOT_GO_MOD"
GO_TOO_NEW = "GO_TOO_NEW"
TOO_LARGE = "TOO_LARGE"
NO_ELIGIBLE_ADVISORY = "NO_ELIGIBLE_ADVISORY"
LOAD_FAILED = "LOAD_FAILED"
NO_MAIN, TOO_MANY_MAINS = "NO_MAIN", "TOO_MANY_MAINS"
BUILD_FAILED = "BUILD_FAILED"
NO_ELIGIBLE_ADVISORY_SELECTED = "NO_ELIGIBLE_ADVISORY_SELECTED"

RULE_OF = {DIVERSITY_OWNER: "A1", DIVERSITY_DOMAIN: "A1", REPO_UNREACHABLE: "A2", NO_TAG_BEFORE_CUTOFF: "A3",
           NO_ROOT_GO_MOD: "A4", GO_TOO_NEW: "A5", TOO_LARGE: "A6", NO_ELIGIBLE_ADVISORY: "A7", LOAD_FAILED: "A8",
           NO_MAIN: "A9", TOO_MANY_MAINS: "A9", BUILD_FAILED: "A10", NO_ELIGIBLE_ADVISORY_SELECTED: "A11",
           KEPT: "A1-A11", NOT_EVALUATED: "quota"}

DOWNLOAD_TIMEOUT_S = 1800.0
BUILD_TIMEOUT_S = 900.0
LIST_TIMEOUT_S = 600.0

_STABLE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_GO_DIRECTIVE = re.compile(r"^go\s+(\d+(?:\.\d+){0,2})\s*$", re.MULTILINE)
_MODULE_LINE = re.compile(r"^module\s+(\S+)", re.MULTILINE)


# --- pure rule functions ---------------------------------------------------------------------------
def seeded_key(seed: int, *parts: str) -> str:
    return hashlib.sha256((f"{seed}:" + ":".join(parts)).encode("utf-8")).hexdigest()


def candidate_order(candidates: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Ascending sha256("<seed>:<repo>"): the file order does not favour any candidate."""
    return sorted(candidates, key=lambda c: seeded_key(seed, c["repo"]))


def owner_of(repo: str) -> str:
    """`github.com/<owner>/<name>` -> lower-case owner."""
    parts = repo.split("/")
    return parts[1].lower() if len(parts) >= 3 else repo.lower()


def stable_tags(refs: dict[str, str]) -> list[tuple[str, str]]:
    """(tag, commit-ish) of tags `vMAJOR.MINOR.PATCH` only, highest version first. `refs` maps tag
    names to the SHA to fetch (peeled when the listing gave one)."""
    out = []
    for name, sha in refs.items():
        m = _STABLE_TAG.match(name)
        if m:
            out.append(((int(m.group(1)), int(m.group(2)), int(m.group(3))), name, sha))
    out.sort(key=lambda t: t[0], reverse=True)
    return [(name, sha) for _, name, sha in out]


def parse_ls_remote(text: str) -> dict[str, str]:
    """`git ls-remote --tags` output -> {tag: sha}; a peeled `^{}` line (the commit of an
    annotated tag) replaces the tag object's SHA."""
    refs: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        sha, ref = parts
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            peeled[name[:-3]] = sha
        else:
            refs[name] = sha
    refs.update({k: v for k, v in peeled.items() if k in refs})
    return refs


def parse_go_mod(text: str) -> dict[str, Any]:
    """module path, `go` directive, require entries {path: version} (direct and indirect, block and
    single-line forms) and the paths that a `replace` directive redirects."""
    module = _MODULE_LINE.search(text)
    go = _GO_DIRECTIVE.search(text)
    requires: dict[str, str] = {}
    replaced: set[str] = set()
    block = None
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if block:
            if line == ")":
                block = None
                continue
            body = line
        else:
            m = re.match(r"^(require|replace|exclude|retract|tool|godebug|ignore)\s*\($", line)
            if m:
                block = m.group(1)
                continue
            m = re.match(r"^(require|replace)\s+(.+)$", line)
            if not m:
                continue
            block_kind, body = m.group(1), m.group(2)
            _apply(block_kind, body, requires, replaced)
            continue
        _apply(block, body, requires, replaced)
    return {"module": module.group(1).strip('"') if module else None, "go": go.group(1) if go else None,
            "requires": requires, "replaced": sorted(replaced)}


def _apply(kind: str, body: str, requires: dict[str, str], replaced: set[str]) -> None:
    toks = body.replace('"', "").split()
    if kind == "require" and len(toks) >= 2:
        requires[toks[0]] = toks[1]
    elif kind == "replace" and "=>" in toks:
        replaced.add(toks[0])


def go_version_tuple(v: str | None) -> tuple[int, ...]:
    """'1.24' / '1.24.0' / 'go1.26.10' -> (1, 24, 0); None or junk -> (0,)."""
    if not v:
        return (0,)
    m = re.match(r"^(?:go)?(\d+)(?:\.(\d+))?(?:\.(\d+))?", v.strip())
    if not m:
        return (0,)
    return tuple(int(x or 0) for x in m.groups())


def go_directive_ok(go_directive: str | None, toolchain: str) -> bool:
    """A5: the go directive is not newer than the local toolchain (a missing directive means go 1.16)."""
    return go_version_tuple(go_directive or "1.16") <= go_version_tuple(toolchain)


def _version(v: str) -> GoVersion | None:
    s = v.strip()
    if s in ("0", ""):
        return parse_version("v0.0.0-0")    # the lowest version: "introduced: 0" means from the start
    try:
        return parse_version(s)
    except InvalidVersion:
        return None


def version_affected(version: str, events: list[dict[str, str]]) -> bool | None:
    """V2/V3: is `version` inside the vulndb `versions` ranges (OSV SEMVER semantics: events in
    ascending order, `introduced` opens a range, `fixed` closes it, a list that starts with
    `fixed` is open from the start)? None if a version cannot be parsed. `+incompatible` is
    ignored for ordering (semver build metadata)."""
    v = _version(version)
    if v is None:
        return None
    evs = []
    for e in events or []:
        for kind in ("introduced", "fixed"):
            if kind in e:
                ev = _version(str(e[kind]))
                if ev is None:
                    return None
                evs.append((kind, ev))
    if not evs:
        return True                         # no versions listed: every version is affected
    if evs[0][0] == "fixed":
        evs.insert(0, ("introduced", _version("0")))
    affected = False
    for kind, ev in evs:
        if v >= ev:
            affected = kind == "introduced"
        else:
            break
    return affected


def advisory_index(cache_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """V1 applied to the pinned snapshot: {module path: [entries]} for every D1-eligible report and
    every module entry of it that has core symbols, with its raw `versions` events."""
    cases, _ = datasets.load_all_cases(cache_dir)
    index: dict[str, list[dict[str, Any]]] = {}
    rdir = vulndb.reports_dir(cache_dir)
    for case in cases:
        if not datasets.eligible_for_d1(case):
            continue
        raw = yaml.safe_load((rdir / f"{case['id']}.yaml").read_text(encoding="utf-8")) or {}
        raw_versions = {m.get("module"): m.get("versions") or [] for m in raw.get("modules") or []}
        for m in case["modules"]:
            if not any(p["core_symbols"] for p in m["packages"]):
                continue
            index.setdefault(m["module"], []).append({
                "id": case["id"], "module": m["module"], "events": raw_versions.get(m["module"], []),
                "created": case.get("created"), "fix_commit": case["fix_commits"][0],
                "packages": [p["package"] for p in m["packages"] if p["core_symbols"]],
                "core_symbols": sum(len(p["core_symbols"]) for p in m["packages"])})
    return index


def eligible_advisories(versions: dict[str, str], index: dict[str, list[dict[str, Any]]],
                        replaced: list[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """V2 (or V3 with build-list versions): (eligible, unparseable). A module that a `replace`
    directive redirects is not judged by its required version (its code comes from elsewhere)."""
    out, bad = [], []
    skip = set(replaced or [])
    for path, ver in sorted(versions.items()):
        if path in skip:
            continue
        for entry in index.get(path, []):
            hit = version_affected(ver, entry["events"])
            if hit is None:
                bad.append({"id": entry["id"], "module": path, "version": ver})
            elif hit:
                out.append({**{k: entry[k] for k in ("id", "module", "created", "fix_commit", "packages",
                                                     "core_symbols")}, "version": ver})
    return out, bad


def pick_cases(app_repo: str, eligible: list[dict[str, Any]], seed: int, max_cases: int) -> list[dict[str, Any]]:
    """Round-robin over modules (seeded order), advisories of each module in seeded order, one per
    module per round, until `max_cases` are taken. An advisory listed under two modules counts once."""
    by_module: dict[str, list[dict[str, Any]]] = {}
    for e in eligible:
        by_module.setdefault(e["module"], []).append(e)
    modules = sorted(by_module, key=lambda m: seeded_key(seed, app_repo, m))
    queues = {m: sorted(by_module[m], key=lambda e: seeded_key(seed, app_repo, e["id"])) for m in modules}
    picked, seen = [], set()
    while len(picked) < max_cases and any(queues.values()):
        for m in modules:
            while queues[m] and queues[m][0]["id"] in seen:
                queues[m].pop(0)
            if queues[m] and len(picked) < max_cases:
                e = queues[m].pop(0)
                seen.add(e["id"])
                picked.append(e)
    return picked


# --- probes (network, git, go) ---------------------------------------------------------------------
def go_selection_env(gomodcache: Path, proxy: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.update(GOTOOLCHAIN="local", CGO_ENABLED="0", GOMODCACHE=str(gomodcache), GOWORK="off",
               GOFLAGS="-mod=readonly", GOPROXY="https://proxy.golang.org" if proxy else "off",
               GOSUMDB="sum.golang.org" if proxy else "off")
    return env


def first_line(text: str | None, limit: int = 300) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


@dataclass
class Probe:
    """The network and toolchain steps of the rules. Every method returns data or an error line;
    none raises for a repository problem."""
    cache_root: Path
    work_root: Path
    gomodcache: Path
    runner: Any = subprocess.run
    log: Any = print
    timings: dict[str, float] = field(default_factory=dict)

    def _run(self, args, cwd=None, env=None, timeout=300.0):
        try:
            return self.runner(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 124, "", f"timed out after {timeout:g}s")
        except OSError as exc:
            return subprocess.CompletedProcess(args, 127, "", str(exc))

    def toolchain(self) -> str:
        p = self._run(["go", "env", "GOVERSION"], env=go_selection_env(self.gomodcache, False), timeout=60)
        return p.stdout.strip() if p.returncode == 0 else ""

    def _probe_dir(self, repo: str) -> Path:
        d = self.cache_root / "d3probe" / repo
        if not (d / ".git").is_dir():
            d.mkdir(parents=True, exist_ok=True)
            self._run(["git", "init", "-q"], cwd=d)
            self._run(["git", "remote", "add", "origin", "https://" + repo], cwd=d)
        return d

    def list_tags(self, repo: str) -> tuple[dict[str, str] | None, str | None]:
        p = self._run(["git", "ls-remote", "--tags", "https://" + repo], timeout=120)
        if p.returncode != 0:
            return None, first_line(p.stderr) or f"git ls-remote exited {p.returncode}"
        return parse_ls_remote(p.stdout), None

    def tag_commit(self, repo: str, tag: str) -> tuple[str | None, str | None, str | None]:
        """(commit sha, committer date ISO, error) of a tag, fetched without blobs."""
        d = self._probe_dir(repo)
        f = self._run(["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin",
                       f"refs/tags/{tag}:refs/tags/{tag}"], cwd=d, timeout=300)
        if f.returncode != 0:
            return None, None, "git fetch: " + first_line(f.stderr)
        p = self._run(["git", "log", "-1", "--format=%H %cI", f"{tag}^{{commit}}"], cwd=d)
        if p.returncode != 0 or not p.stdout.strip():
            return None, None, "git log: " + first_line(p.stderr)
        sha, date = p.stdout.split()
        return sha, date, None

    def file_at(self, repo: str, sha: str, path: str) -> str | None:
        p = self._run(["git", "show", f"{sha}:{path}"], cwd=self._probe_dir(repo), timeout=300)
        return p.stdout if p.returncode == 0 else None

    def prepare(self, repo: str, sha: str) -> tuple[Path | None, str | None]:
        """A8 first half: the pinned tree (git archive of a depth-1 fetch) and its dependencies
        (`go mod download`, read-only go.mod)."""
        from vulntrace.eval import lift_prep

        owner, name = repo.split("/")[1:3]
        repo_dir = git_fetch.repo_cache_dir("github.com", owner, name, self.cache_root / "repos")
        try:
            git_fetch.fetch_commit("github.com", owner, name, sha, depth=1, cache_root=self.cache_root / "repos",
                                   timeout=900.0)
        except git_fetch.GitFetchError as exc:
            return None, f"fetch: {exc.message}"
        dest = app_tree_dir(self.work_root, repo, sha)
        if not (dest / "go.mod").is_file():
            shutil.rmtree(dest, ignore_errors=True)
            err = lift_prep.extract_tree(repo_dir, sha, dest)
            if err:
                return None, err
        self.gomodcache.mkdir(parents=True, exist_ok=True)
        p = self._run(["go", "mod", "download"], cwd=dest, env=go_selection_env(self.gomodcache, True),
                      timeout=DOWNLOAD_TIMEOUT_S)
        if p.returncode != 0:
            return dest, "go mod download: " + first_line(p.stderr or p.stdout)
        return dest, None

    def list_mains(self, module_dir: Path) -> tuple[list[str] | None, list[str], str | None]:
        """A8 second half and A9: (main packages that list cleanly, package errors, fatal error)."""
        from vulntrace.pipeline import app as app_mod

        p = self._run(["go", "list", "-e", "-json=ImportPath,Name,Error,DepsErrors,Dir", "./..."], cwd=module_dir,
                      env=go_selection_env(self.gomodcache, False), timeout=LIST_TIMEOUT_S)
        if p.returncode != 0 and not p.stdout.strip():
            return None, [], first_line(p.stderr) or f"go list exited {p.returncode}"
        pkgs, dec, i, text = [], json.JSONDecoder(), 0, p.stdout
        while i < len(text):
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                break
            try:
                obj, i = dec.raw_decode(text, i)
            except json.JSONDecodeError:
                return None, [], "go list printed malformed JSON"
            pkgs.append(obj)
        mains, errors = app_mod.find_mains(pkgs)
        return mains, errors, None

    def build(self, module_dir: Path, main: str) -> str | None:
        """A10: compile one main package to a temporary file; the file is deleted, never run."""
        with tempfile.TemporaryDirectory(prefix="vt-d3-build-") as td:
            p = self._run(["go", "build", "-o", str(Path(td) / "bin"), main], cwd=module_dir,
                          env=go_selection_env(self.gomodcache, False), timeout=BUILD_TIMEOUT_S)
        return None if p.returncode == 0 else first_line(p.stderr or p.stdout) or f"go build exited {p.returncode}"

    def selected_versions(self, module_dir: Path, paths: list[str]) -> tuple[dict[str, str], str | None]:
        """A11: the build list's version of each path (`go list -m`; the proxy may be asked for
        go.mod files of the module graph, nothing is built)."""
        if not paths:
            return {}, None
        p = self._run(["go", "list", "-m", "-json", *paths], cwd=module_dir,
                      env=go_selection_env(self.gomodcache, True), timeout=LIST_TIMEOUT_S)
        if p.returncode != 0 and not p.stdout.strip():
            return {}, "go list -m: " + first_line(p.stderr)
        out, dec, i, text = {}, json.JSONDecoder(), 0, p.stdout
        while i < len(text):
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                break
            obj, i = dec.raw_decode(text, i)
            if obj.get("Replace"):
                continue          # replaced: the code is not the advisory module's
            if obj.get("Path") and obj.get("Version"):
                out[obj["Path"]] = obj["Version"]
        return out, None


def app_tree_dir(work_root: Path, repo: str, sha: str) -> Path:
    return Path(work_root) / repo.replace("/", "_") / sha[:12]


# --- the selection ---------------------------------------------------------------------------------
def select(config: dict[str, Any], index: dict[str, list[dict[str, Any]]], probe: Probe, toolchain: str,
           log=print) -> dict[str, Any]:
    """Apply A1-A11 and V1-V3 in order; every candidate gets a record."""
    seed, max_apps = config["seed"], config["max_apps"]
    cutoff = config["pin_cutoff"]
    ordered = candidate_order(config["candidates"], seed)
    kept: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for pos, cand in enumerate(ordered, start=1):
        repo = cand["repo"]
        rec: dict[str, Any] = {"order": pos, "repo": repo, "domain": cand["domain"], "owner": owner_of(repo)}
        records.append(rec)
        if len(kept) >= max_apps:
            _done(rec, NOT_EVALUATED, "five applications were already kept", log)
            continue
        if any(k["owner"] == rec["owner"] for k in kept):
            _done(rec, DIVERSITY_OWNER, f"owner {rec['owner']} already kept", log)
            continue
        if any(k["domain"] == cand["domain"] for k in kept):
            _done(rec, DIVERSITY_DOMAIN, f"domain {cand['domain']} already kept", log)
            continue
        app = evaluate_candidate(rec, config, index, probe, toolchain, cutoff, log)
        if app is not None:
            kept.append(rec)
    return {"records": records, "kept": [r for r in records if r["status"] == KEPT]}


def _done(rec: dict[str, Any], status: str, detail: str, log) -> None:
    rec["status"], rec["rule"], rec["detail"] = status, RULE_OF[status], detail
    log(f"[{rec['order']:2d}] {rec['repo']:42s} {status:30s} ({RULE_OF[status]}) {detail}")


def evaluate_candidate(rec: dict[str, Any], config: dict[str, Any], index: dict[str, list[dict[str, Any]]],
                       probe: Probe, toolchain: str, cutoff: str, log) -> dict[str, Any] | None:
    repo = rec["repo"]
    refs, err = probe.list_tags(repo)
    if refs is None:
        _done(rec, REPO_UNREACHABLE, err or "", log)
        return None
    tags = stable_tags(refs)
    rec["stable_tags"] = len(tags)
    pin = None
    probed = 0
    for tag, _ in tags[: config["max_tag_probes"]]:
        probed += 1
        sha, date, terr = probe.tag_commit(repo, tag)
        if sha is None:
            rec.setdefault("tag_errors", []).append(f"{tag}: {terr}")
            continue
        if _utc(date) <= _utc(cutoff):
            pin = {"tag": tag, "commit": sha, "commit_date": date}
            break
    rec["tags_probed"] = probed
    if pin is None:
        _done(rec, NO_TAG_BEFORE_CUTOFF, f"{len(tags)} stable tags, {probed} probed, none dated on or before {cutoff}", log)
        return None
    rec["pin"] = pin
    text = probe.file_at(repo, pin["commit"], "go.mod")
    gm = parse_go_mod(text) if text else None
    if not gm or not gm["module"]:
        _done(rec, NO_ROOT_GO_MOD, f"{pin['tag']}: no go.mod with a module line at the root", log)
        return None
    rec["module"], rec["go_directive"], rec["requires"] = gm["module"], gm["go"], len(gm["requires"])
    if not go_directive_ok(gm["go"], toolchain):
        _done(rec, GO_TOO_NEW, f"{pin['tag']}: go {gm['go']} > {toolchain}", log)
        return None
    if len(gm["requires"]) > config["max_requires"]:
        _done(rec, TOO_LARGE, f"{pin['tag']}: {len(gm['requires'])} require entries > {config['max_requires']}", log)
        return None
    elig, bad = eligible_advisories(gm["requires"], index, gm["replaced"])
    rec["eligible_by_go_mod"] = sorted({e["id"] for e in elig})
    rec["unparseable_versions"] = bad
    if not elig:
        _done(rec, NO_ELIGIBLE_ADVISORY, f"{pin['tag']}: no D1-eligible advisory covers a required version", log)
        return None
    module_dir, perr = probe.prepare(repo, pin["commit"])
    if perr:
        _done(rec, LOAD_FAILED, f"{pin['tag']}: {perr}", log)
        return None
    mains, pkg_errors, lerr = probe.list_mains(module_dir)
    rec["package_errors"] = pkg_errors[:5]
    if lerr or mains is None:
        _done(rec, LOAD_FAILED, f"{pin['tag']}: {lerr}", log)
        return None
    rec["mains"] = mains
    if not mains:
        _done(rec, NO_MAIN, f"{pin['tag']}: no main package lists cleanly ({len(pkg_errors)} package errors)", log)
        return None
    if len(mains) > config["max_mains"]:
        _done(rec, TOO_MANY_MAINS, f"{pin['tag']}: {len(mains)} main packages > {config['max_mains']}", log)
        return None
    for m in mains:
        berr = probe.build(module_dir, m)
        if berr:
            _done(rec, BUILD_FAILED, f"{pin['tag']}: {m}: {berr}", log)
            return None
    selected, serr = probe.selected_versions(module_dir, sorted({e["module"] for e in elig}))
    rec["selected_versions"] = selected
    if serr:
        _done(rec, LOAD_FAILED, f"{pin['tag']}: {serr}", log)
        return None
    elig_sel, _ = eligible_advisories(selected, index)
    elig_sel = [e for e in elig_sel if e["id"] in set(rec["eligible_by_go_mod"])]
    rec["eligible_selected"] = sorted({e["id"] for e in elig_sel})
    if not elig_sel:
        _done(rec, NO_ELIGIBLE_ADVISORY_SELECTED, f"{pin['tag']}: build-list versions are outside every range", log)
        return None
    gomod_ver = gm["requires"]
    rec["cases"] = [{"advisory": e["id"], "module": e["module"], "version_go_mod": gomod_ver.get(e["module"]),
                     "version_selected": e["version"], "created": e["created"], "fix_commit": e["fix_commit"],
                     "packages": e["packages"]}
                    for e in pick_cases(repo, elig_sel, config["seed"], config["max_cases_per_app"])]
    _done(rec, KEPT, f"{pin['tag']} ({pin['commit'][:12]}), {len(mains)} main(s), "
                     f"{len(elig_sel)} eligible advisories, {len(rec['cases'])} taken", log)
    return rec


def _utc(iso: str) -> str:
    """ISO timestamp -> comparable UTC string 'YYYY-MM-DDTHH:MM:SS'."""
    from datetime import datetime, timezone

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def diversity_note(kept: list[dict[str, Any]]) -> str:
    owners = [k["owner"] for k in kept]
    domains = [k["domain"] for k in kept]
    dup = len(set(owners)) != len(owners) or len(set(domains)) != len(domains)
    return (f"{len(kept)} applications, {len(set(owners))} distinct owners, {len(set(domains))} distinct domains "
            f"({', '.join(domains)}); " + ("DUPLICATE owner or domain" if dup else
                                           "no two share an owner or a domain (fork relations are not checked by code)"))


def case_list(kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The committed D3 case list: one row per (application, advisory)."""
    rows = []
    for k in kept:
        for c in k["cases"]:
            rows.append({"id": f"{k['repo'].split('/')[-1]}__{c['advisory']}", "app_repo": k["repo"],
                         "app_url": "https://" + k["repo"], "app_tag": k["pin"]["tag"], "app_commit": k["pin"]["commit"],
                         "app_module": k["module"], "app_domain": k["domain"], "mains": k["mains"], **c})
    return rows
