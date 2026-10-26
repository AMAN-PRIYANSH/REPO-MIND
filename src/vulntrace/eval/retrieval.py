"""Mode 2 retrieval evaluation harness (CP4 deliverable 6):
`python -m vulntrace eval retrieval --config <name>`.

Configurations (a name, plus a chunk variant for the retrieval ones):

| name | ranking of a case's candidates |
|---|---|
| `random` | seeded random order (the floor every Recall@k must beat) |
| `size` | E0-style: largest function body first |
| `bid` | B-ID: candidates touched by commits naming the advisory, then the rest (both seeded random) |
| `bid-only` | B-ID strict: only the candidates B-ID predicts; an abstention finds nothing |
| `bm25` | BM25 over the range's chunks |
| `dense:<embedder>` | cosine similarity to the query embedding |
| `hybrid:<embedder>` | RRF (k=60) of `bm25` and `dense:<embedder>` |
| `hybrid+rerank:<embedder>+<reranker>` | the top 50 of `hybrid:<embedder>` re-ordered by a cross-encoder |

The first four ignore the chunk text and are run once (variant `-`). Each run writes one JSON
file of compact per-case rows; `cases.json` holds the per-case facts (cluster, buckets, gold
counts) once; the results document is rendered from these files by code.
"""

import dataclasses
import json
import platform
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import baselines, datasets
from vulntrace.eval import retrieval_metrics as rm
from vulntrace.eval.run_info import run_info
from vulntrace.retrieval import bm25 as bm25_mod
from vulntrace.retrieval import chunking, dense, fusion, ranking, rerank
from vulntrace.retrieval.query import build_query, query_input_from_case
from vulntrace.retrieval.tokenize import code_tokens
from vulntrace.retrieval.vectorstore import InMemoryVectorStore, VectorStore

SCHEMA_VERSION = "1.0"
NO_VARIANT = "-"
TEXT_FREE = ("random", "size", "bid", "bid-only")
SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE = "<=10", "11-100", ">100"


class HarnessError(Exception):
    pass


def size_bucket(n: int) -> str:
    return SIZE_SMALL if n <= 10 else (SIZE_MEDIUM if n <= 100 else SIZE_LARGE)


@dataclass(frozen=True)
class Config:
    name: str
    kind: str
    embedder: str | None = None
    reranker: str | None = None

    @property
    def text_free(self) -> bool:
        return self.kind in TEXT_FREE


def parse_config(name: str) -> Config:
    from vulntrace.models.registry import EMBEDDERS, RERANKERS

    if name in TEXT_FREE or name == "bm25":
        return Config(name, name)
    kind, _, arg = name.partition(":")
    if kind in ("dense", "hybrid") and arg in EMBEDDERS:
        return Config(name, kind, embedder=arg)
    if kind == "hybrid+rerank":
        emb, _, rr = arg.partition("+")
        if emb in EMBEDDERS and rr in RERANKERS:
            return Config(name, kind, embedder=emb, reranker=rr)
    raise HarnessError(f"unknown config {name!r}; expected one of random, size, bid, bid-only, bm25, dense:<e>, "
                       f"hybrid:<e>, hybrid+rerank:<e>+<r> with e in {sorted(EMBEDDERS)} and r in {sorted(RERANKERS)}")


@dataclass
class EvalCase:
    case_id: str
    created: str | None
    cluster_key: str
    range_key: str
    status: str
    candidate_ids: list[str]
    gold_core: set[str]
    gold_core_derived: set[str]
    query: str
    bid_ids: set[str]
    bid_matched: bool
    body_len: dict[str, int] = field(default_factory=dict)
    query_has_details: bool = False
    query_names_gold: bool = False
    summary: str = ""   # the two advisory fields the query is built from (CP5 prompts take the same two)
    details: str = ""

    def facts(self, cutoff: str) -> dict[str, Any]:
        n = len(self.candidate_ids)
        return {"id": self.case_id, "cluster_key": self.cluster_key, "range_key": self.range_key,
                "date_bucket": datasets.date_bucket(self.created, cutoff), "size_bucket": size_bucket(n),
                "status": self.status, "n_candidates": n, "n_gold_core": len(self.gold_core),
                "n_gold_core_derived": len(self.gold_core_derived),
                "query_has_advisory_id": chunking.has_advisory_id(self.query),
                "query_chars": len(self.query), "query_has_details": self.query_has_details,
                "query_names_gold": self.query_names_gold,
                "bid_matched": self.bid_matched,
                "bid_predicted_count": len(self.bid_ids)}


def query_names_symbol(query: str, symbols: set[str]) -> bool:
    """Whether the advisory text names one of the gold functions (its bare name, after any
    `Type.`, as a case-sensitive whole word). Legitimate advisory text, not a leak, but it
    hands lexical retrieval a direct hit, so results are also reported without such cases.
    Evaluation-side only: the query builder never sees the symbols."""
    names = {s.rsplit(".", 1)[-1] for s in symbols}
    return any(re.search(r"\b" + re.escape(n) + r"\b", query) for n in names if n)


def bid_candidate_ids(case: dict[str, Any], rr: dict[str, Any]) -> tuple[set[str], bool]:
    """B-ID (CP3 baseline) at candidate level: ids touched by a commit whose subject or body
    names one of the advisory's identifiers; and whether any commit matched at all."""
    ids = baselines.advisory_identifiers(case)
    known = {c["candidate_id"] for c in rr["candidates"]}
    out, matched = set(), False
    for commit in rr["commits"]:
        text = f"{commit['subject']}\n{commit['body']}".upper()
        if any(i in text for i in ids):
            matched = True
            out.update(c for c in commit["touches_candidates"] if c in known)
    return out, matched


def load_eval_set(case_list: dict[str, Any], cases_by_id: dict[str, dict], data_dir: Path,
                  allow_missing: bool = False) -> tuple[list[EvalCase], dict[str, list[chunking.Chunk]], dict]:
    """Every case of the committed D4 list, with its chunks shared per range. Missing evidence
    is an error unless `allow_missing` (then such a case is scored as a miss and counted)."""
    rr_dir, code_dir = Path(data_dir) / "release_range", Path(data_dir) / "candidate_code"
    cases: list[EvalCase] = []
    ranges: dict[str, list[chunking.Chunk]] = {}
    signature: dict[str, list] = {}
    notes = {"missing_evidence": [], "range_splits": []}
    for entry in sorted(case_list["cases"], key=lambda c: c["id"]):
        cid = entry["id"]
        vc = cases_by_id.get(cid)
        rr_p, code_p = rr_dir / f"{cid}.json", code_dir / f"{cid}.json"
        if vc is None or not rr_p.is_file() or not code_p.is_file():
            if not allow_missing:
                raise HarnessError(f"no evidence for {cid} in {data_dir} (run `python -m vulntrace dataset "
                                   "materialize --set d4` first)")
            notes["missing_evidence"].append(cid)
            rr, code = None, None
        else:
            rr = json.loads(rr_p.read_text(encoding="utf-8"))
            code = json.loads(code_p.read_text(encoding="utf-8"))
        cluster = (datasets.d4_cluster_key(vc) if vc else None) or cid
        range_key = cluster
        cands = rr["candidates"] if rr else []
        sig = [(c["candidate_id"], c["symbol"], c["package_dir"]) for c in cands]
        if range_key in signature and signature[range_key] != sig:
            range_key = f"{cluster}#{cid}"  # same versions but different evidence: do not share
            notes["range_splits"].append(cid)
        if rr and range_key not in ranges:
            fc = vc["fix_commits"][0]
            ranges[range_key] = chunking.build_chunks(range_key, rr, code, fc["owner"], fc["repo"])
            signature[range_key] = sig
        core = baselines.core_symbols(vc) if vc else set()
        core_derived = baselines.core_and_derived_symbols(vc) if vc else set()
        bid_ids, matched = bid_candidate_ids(vc, rr) if rr else (set(), False)
        chunks = ranges.get(range_key, [])
        cases.append(EvalCase(
            case_id=cid, created=entry.get("created"), cluster_key=cluster, range_key=range_key,
            status=rr["status"] if rr else "MISSING", candidate_ids=[c["candidate_id"] for c in cands],
            gold_core={c["candidate_id"] for c in cands if c["symbol"] in core},
            gold_core_derived={c["candidate_id"] for c in cands if c["symbol"] in core_derived},
            query=build_query(query_input_from_case(vc)) if vc else "",
            summary=query_input_from_case(vc).summary if vc else "", details=query_input_from_case(vc).details if vc else "",
            bid_ids=bid_ids, bid_matched=matched,
            body_len={c.candidate_id: len(c.body) for c in chunks},
            query_has_details=bool(vc and query_input_from_case(vc).details.strip()),
            query_names_gold=bool(vc and query_names_symbol(build_query(query_input_from_case(vc)), core)),
        ))
    return cases, ranges, notes


class Harness:
    def __init__(self, cases: list[EvalCase], ranges: dict[str, list[chunking.Chunk]], seed: int = ranking.DEFAULT_SEED,
                 embedding_cache_root: Path | None = None, store: VectorStore | None = None, device: str | None = None,
                 rerank_top_n: int = rerank.DEFAULT_TOP_N, log: Callable[[str], None] | None = None):
        self.cases, self.ranges, self.seed = cases, ranges, seed
        self._base_cases = list(cases)
        self.cache_root, self.device, self.rerank_top_n = embedding_cache_root, device, rerank_top_n
        self.store = store or InMemoryVectorStore()
        self.log = log or (lambda msg: None)
        self._bm25: dict[tuple[str, str], tuple[bm25_mod.BM25, list[str]]] = {}
        self._embedders: dict[str, Any] = {}
        self._caches: dict[str, dense.EmbeddingCache] = {}
        self._indexed: set[tuple[str, str]] = set()
        self._rerankers: dict[str, Any] = {}
        self._qvec: dict[tuple[str, str], Any] = {}
        self._dense_rankings: dict[tuple[str, str, str, str], list[str]] = {}
        self.embed_stats: dict[str, dict] = {}

    def set_queries(self, queries: dict[str, str] | None) -> None:
        """Replace the query text of the given cases (HyDE); `None` restores the originals. The
        cached dense rankings depend on the query, so they are dropped."""
        self.cases = [dataclasses.replace(c, query=queries[c.case_id]) if queries and c.case_id in queries else c
                      for c in self._base_cases]
        self._dense_rankings.clear()

    # --- components -----------------------------------------------------------------------
    def _bm25_for(self, range_key: str, variant: str):
        key = (range_key, variant)
        if key not in self._bm25:
            chunks = self.ranges[range_key]
            self._bm25[key] = (bm25_mod.BM25([code_tokens(c.text(variant).text) for c in chunks]),
                               [c.candidate_id for c in chunks])
        return self._bm25[key]

    def embedder(self, alias: str):
        if alias not in self._embedders:
            from vulntrace.models.registry import make_embedder

            e = make_embedder(alias, device=self.device)
            self._embedders[alias] = e
            self._caches[alias] = dense.EmbeddingCache(self.cache_root, e.model_id)
        return self._embedders[alias]

    def reranker(self, alias: str):
        if alias not in self._rerankers:
            from vulntrace.models.registry import make_reranker

            self._rerankers[alias] = make_reranker(alias, device=self.device)
        return self._rerankers[alias]

    def prepare_dense(self, alias: str, variant: str, progress=None) -> dict[str, int]:
        """Embed (cache) and index every chunk text of `variant` for embedder `alias`."""
        e = self.embedder(alias)
        if (alias, variant) in self._indexed:
            return self.embed_stats.get(f"{alias}|{variant}", {})
        cache = self._caches[alias]
        texts = {}
        for chunks in self.ranges.values():
            for c in chunks:
                t = c.text(variant)
                texts[t.content_sha256] = t.text
        stats = dense.embed_missing(e, cache, texts, progress=progress)
        for chunks in self.ranges.values():
            dense.index_chunks(self.store, cache, chunks, variant)
        self._indexed.add((alias, variant))
        self.embed_stats[f"{alias}|{variant}"] = stats
        self.log(f"dense {alias} {variant}: {stats}")
        return stats

    def release_dense(self, alias: str) -> None:
        """Free the store's vectors for one embedder (Colab memory)."""
        if alias in self._embedders:
            self.store.delete({"embedding_model": self._embedders[alias].model_id})
            self._indexed = {k for k in self._indexed if k[0] != alias}
            self._dense_rankings = {k: v for k, v in self._dense_rankings.items() if k[0] != alias}

    # --- rankings -------------------------------------------------------------------------
    def _bm25_ranking(self, case: EvalCase, variant: str) -> list[str]:
        bm, ids = self._bm25_for(case.range_key, variant)
        return ranking.rank(ids, bm.scores(code_tokens(case.query)), case.case_id, self.seed)

    def _dense_ranking(self, case: EvalCase, alias: str, variant: str) -> list[str]:
        key = (alias, variant, case.case_id, case.query)  # the query is part of the key (CP6 agent queries)
        if key not in self._dense_rankings:
            e = self.embedder(alias)
            self.prepare_dense(alias, variant)
            qk = (alias, case.query)
            if qk not in self._qvec:
                self._qvec[qk] = e.embed_query(case.query)
            scores = dense.dense_scores(self.store, self._qvec[qk], case.range_key, variant, e.model_id,
                                        len(case.candidate_ids))
            ids = case.candidate_ids
            self._dense_rankings[key] = ranking.rank(ids, [scores.get(i, float("-inf")) for i in ids],
                                                     case.case_id, self.seed)
        return self._dense_rankings[key]

    def rank_case(self, cfg: Config, case: EvalCase, variant: str) -> list[str]:
        ids = case.candidate_ids
        if not ids:
            return []
        if cfg.kind == "random":
            return ranking.random_ranking(ids, case.case_id, self.seed)
        if cfg.kind == "size":
            return ranking.rank(ids, [float(case.body_len.get(i, 0)) for i in ids], case.case_id, self.seed)
        if cfg.kind in ("bid", "bid-only"):
            hit = [i for i in ids if i in case.bid_ids]
            first = ranking.random_ranking(hit, case.case_id, self.seed)
            if cfg.kind == "bid-only":
                return first
            return first + ranking.random_ranking([i for i in ids if i not in case.bid_ids], case.case_id, self.seed)
        if cfg.kind == "bm25":
            return self._bm25_ranking(case, variant)
        if cfg.kind == "dense":
            return self._dense_ranking(case, cfg.embedder, variant)
        hybrid = fusion.rrf([self._bm25_ranking(case, variant), self._dense_ranking(case, cfg.embedder, variant)],
                            case.case_id, seed=self.seed)
        if cfg.kind == "hybrid":
            return hybrid
        text_of = {c.candidate_id: c.text(variant).text for c in self.ranges[case.range_key]}
        return rerank.rerank(self.reranker(cfg.reranker), case.query, hybrid, text_of, self.rerank_top_n)

    def rank_query(self, cfg: Config, case: EvalCase, variant: str, query: str) -> list[str]:
        """The ranking `rank_case` gives, but for another query text over the same case's candidates
        (the CP6 agent's `search_code`). Same components, same seeded tie-break; for
        `query == case.query` it is exactly `rank_case`."""
        return self.rank_case(cfg, case if query == case.query else dataclasses.replace(case, query=query), variant)

    def run(self, cfg: Config, variant: str) -> dict[str, Any]:
        variant = NO_VARIANT if cfg.text_free else variant
        if not cfg.text_free and variant not in chunking.VARIANTS:
            raise HarnessError(f"unknown variant {variant!r}")
        t0 = time.monotonic()
        if cfg.embedder:
            self.prepare_dense(cfg.embedder, variant)
        t_prep = time.monotonic() - t0
        rows = []
        for case in self.cases:
            r = self.rank_case(cfg, case, variant)
            if sorted(r) != sorted(case.candidate_ids) and cfg.kind != "bid-only":
                raise HarnessError(f"{cfg.name} on {case.case_id}: ranking is not a permutation of the candidates")
            rows.append({"id": case.case_id, "core": rm.ranking_row(r, case.gold_core),
                         "core_derived": rm.ranking_row(r, case.gold_core_derived)})
        models = {}
        if cfg.embedder:
            models["embedder"] = self.embedder(cfg.embedder).info()
            models["embedding_cache"] = self.embed_stats.get(f"{cfg.embedder}|{variant}")
        if cfg.reranker:
            models["reranker"] = self.reranker(cfg.reranker).info()
        return {
            "schema_version": SCHEMA_VERSION, "config": cfg.name, "kind": cfg.kind, "variant": variant,
            "seed": self.seed, "models": models,
            "params": {"bm25_k1": bm25_mod.DEFAULT_K1, "bm25_b": bm25_mod.DEFAULT_B, "rrf_k": fusion.DEFAULT_K,
                       "rerank_top_n": self.rerank_top_n if cfg.reranker else None,
                       "chunk_char_cap": chunking.CHUNK_CHAR_CAP, "commit_char_cap": chunking.COMMIT_CHAR_CAP},
            "timing_seconds": {"prepare": round(t_prep, 2), "rank_all_cases": round(time.monotonic() - t0 - t_prep, 2)},
            "rows": rows,
        }


def run_file_name(config: str, variant: str) -> str:
    slug = config.replace(":", "_").replace("+", "-")
    return f"{slug}__{variant.replace('+', '-') if variant != NO_VARIANT else 'any'}.json"


def cases_document(cases: list[EvalCase], ranges: dict[str, list[chunking.Chunk]], notes: dict,
                   cutoff: str = datasets.CONTAMINATION_CUTOFF) -> dict[str, Any]:
    stats: dict[str, int] = {}
    for chunks in ranges.values():
        for k, v in chunking.chunk_stats(chunks).items():
            stats[k] = stats.get(k, 0) + v
    return {"schema_version": SCHEMA_VERSION, "dataset": "D4", "cutoff": cutoff,
            "rclone_cluster": datasets.RCLONE_CLUSTER, "range_count": len(ranges),
            "cluster_count": len({c.cluster_key for c in cases}), "chunk_stats": stats,
            "chunk_char_cap": chunking.CHUNK_CHAR_CAP, "commit_char_cap": chunking.COMMIT_CHAR_CAP,
            "notes": notes, "cases": [c.facts(cutoff) for c in cases]}


def environment(argv: list[str], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run provenance. GPU details are read only if torch is already loaded (a real-model
    run); the base install never imports it. Pass `base` (an earlier call's result) to keep
    the git state captured before this run wrote its own output files."""
    env = dict(base) if base else {**run_info(argv), "platform": platform.platform(),
                                   "python_full": sys.version.split()[0]}
    torch = sys.modules.get("torch")
    if torch is not None:
        try:
            env["torch"] = torch.__version__
            env["cuda_available"] = bool(torch.cuda.is_available())
            env["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        except Exception as exc:
            env["gpu_error"] = repr(exc)
    return env


def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path
