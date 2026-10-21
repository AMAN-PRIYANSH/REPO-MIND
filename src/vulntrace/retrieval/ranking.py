"""Turning scores into a full ranking, with deterministic tie-breaking.

Ties are common (BM25 gives 0 to every chunk that shares no query term). Breaking them by
candidate order would rank files alphabetically, a hidden systematic bias; instead ties are
broken by a seeded hash of (seed, group, item), which is effectively random but reproducible.
The same rule produces the seeded random baseline (every score equal)."""

import hashlib

DEFAULT_SEED = 20261021


def tie_key(seed: int, group: str, item: str) -> str:
    return hashlib.sha256(f"{seed}|{group}|{item}".encode("utf-8")).hexdigest()


def rank(items: list[str], scores: list[float], group: str, seed: int = DEFAULT_SEED) -> list[str]:
    """`items` ordered by descending score; ties by `tie_key`."""
    if len(items) != len(scores):
        raise ValueError("items and scores must have the same length")
    order = sorted(range(len(items)), key=lambda i: (-scores[i], tie_key(seed, group, items[i])))
    return [items[i] for i in order]


def random_ranking(items: list[str], group: str, seed: int = DEFAULT_SEED) -> list[str]:
    return rank(items, [0.0] * len(items), group, seed)
