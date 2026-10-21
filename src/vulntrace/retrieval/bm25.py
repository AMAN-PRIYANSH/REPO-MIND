"""BM25 (Okapi), implemented here with no dependency (CP4 deliverable 3).

score(q, d) = sum over query tokens t (repeats count, i.e. query term frequency is a linear
weight) of  idf(t) * tf(t, d) * (k1 + 1) / (tf(t, d) + k1 * (1 - b + b * |d| / avgdl))

idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))   (the Lucene form: never negative)

Defaults k1 = 1.2, b = 0.75 (the usual values; not tuned on D4). The corpus is one release
range's candidate chunks, never the whole repository.
"""

import math
from collections import Counter

DEFAULT_K1 = 1.2
DEFAULT_B = 0.75


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = DEFAULT_K1, b: float = DEFAULT_B):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.tfs = [Counter(d) for d in docs]
        self.lengths = [len(d) for d in docs]
        self.avgdl = (sum(self.lengths) / self.n) if self.n else 0.0
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        self.df = df
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for i, tf in enumerate(self.tfs):
            for t, c in tf.items():
                self._postings.setdefault(t, []).append((i, c))

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query: list[str]) -> list[float]:
        out = [0.0] * self.n
        if not self.n or self.avgdl == 0:
            return out
        for term, qtf in Counter(query).items():
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = self.idf(term)
            for i, tf in postings:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avgdl)
                out[i] += qtf * idf * tf * (self.k1 + 1) / (tf + norm)
        return out
