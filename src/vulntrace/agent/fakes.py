"""Fake tools for agent tests (CP6 deliverable 3): a small synthetic `CaseWorld` whose search is a
token-overlap ranking, so tests need no evidence, retriever, embedder or model. Combined with
`models.fakes.SequenceLLMClient` (scripted replies) every path of the graph can be driven."""

from vulntrace.agent.world import CaseWorld, Candidate, Commit
from vulntrace.retrieval.query import QueryInput
from vulntrace.retrieval.tokenize import code_tokens

FAKE_CANDIDATES = (
    ("r1", "example.com/m/fs", "cleanPath", "func cleanPath(p string) string", "return filepath.Clean(p)"),
    ("r2", "example.com/m/fs", "Local.Move", "func (f *Local) Move(src, dst string) error", "return os.Rename(cleanPath(src), dst)"),
    ("r3", "example.com/m/fs", "Local.List", "func (f *Local) List(dir string) ([]string, error)", "return readDir(dir)"),
    ("r4", "example.com/m/config", "Config.Load", "func (c *Config) Load() error", "return yaml.Unmarshal(c.raw, c)"),
)
FAKE_COMMITS = (
    ("1111111111111111111111111111111111111111", "fs: reject .. in cleanPath", "Fixes a path traversal.", ("r1",)),
    ("2222222222222222222222222222222222222222", "config: tidy", "", ("r4",)),
)


def fake_world(case_id: str = "GO-2026-0001", graph: bool = True, diffs: bool = True, search=None) -> CaseWorld:
    cands = {cid: Candidate(cid, pkg, sym, f"{pkg.rsplit('/', 1)[-1]}/{sym.lower()}.go", 10, 20, "BOTH", "OLD", sig,
                            f"// {sym} does a thing.", f"{sig} {{\n\t{body}\n}}")
             for cid, pkg, sym, sig, body in FAKE_CANDIDATES}
    commits = [Commit(sha, subj, body, touches) for sha, subj, body, touches in FAKE_COMMITS]

    def overlap_search(query: str) -> list[str]:
        q = set(code_tokens(query))
        score = {cid: len(q & set(code_tokens(c.symbol + " " + c.body))) for cid, c in cands.items()}
        return sorted(cands, key=lambda cid: (-score[cid], cid))

    search = search or overlap_search
    advisory = QueryInput("Path traversal in cleanPath", "cleanPath does not reject .. elements.")
    world = CaseWorld(case_id, advisory, cands, commits, search, search(advisory.summary + " " + advisory.details))
    if diffs:
        world.commit_diffs = {commits[0].sha: {"diff": "--- a/fs/p.go\n+++ b/fs/p.go\n+\tif strings.Contains(p, \"..\") {",
                                               "error": None}}
    if graph:
        world.graph = {"r1": {"status": "FOUND", "callers": [{"package": "example.com/m/fs", "symbol": "Local.Move",
                                                              "candidate_id": "r2", "file": "fs/local.go", "line": 12,
                                                              "kind": "STATIC"}], "callees": []},
                       "r2": {"status": "FOUND", "callers": [], "callees": [
                           {"package": "example.com/m/fs", "symbol": "cleanPath", "candidate_id": "r1", "file": "fs/local.go",
                            "line": 12, "kind": "STATIC"},
                           {"package": "os", "symbol": "Rename", "candidate_id": None, "file": "fs/local.go", "line": 12,
                            "kind": "STATIC"}]}}
    return world


def broken_search(query: str) -> list[str]:
    raise RuntimeError("index unavailable")
