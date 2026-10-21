"""The CP4 evaluation grid, in code rather than only in the Colab notebook (PROJECT_STRUCTURE
rule: notebooks only call project code). The notebook prints and runs these commands; tests
check that every configuration here parses and that the grid stays within Q6 (at most two
embedders and two rerankers)."""

EMBEDDERS = ("bge-small", "codesearch")
RERANKERS = ("minilm", "bge-reranker")
BASELINES = ("random", "size", "bid", "bid-only")


def configs(gpu: bool = True, dry_run: bool = False) -> list[list[str]]:
    """Groups of `--config` values, one `eval retrieval` call per group (so each embedder's
    vectors are freed before the next is loaded). Without a GPU only the small configurations
    run (one embedder, no reranking). `dry_run` swaps every real model for the fakes."""
    embedders = EMBEDDERS if gpu else EMBEDDERS[:1]
    rerankers = RERANKERS if gpu else ()
    groups = [list(BASELINES) + ["bm25"]]
    for e in embedders:
        g = [f"dense:{e}", f"hybrid:{e}"] + [f"hybrid+rerank:{e}+{r}" for r in rerankers]
        groups.append(g)
    if dry_run:
        groups = [[c.replace("bge-small", "fake").replace("codesearch", "fake").replace("minilm", "fake")
                   .replace("bge-reranker", "fake") for c in g] for g in groups]
        seen, out = set(), []
        for g in groups:
            g2 = []
            for c in g:
                if c not in seen:
                    seen.add(c)
                    g2.append(c)
            if g2:
                out.append(g2)
        groups = out
    return groups
