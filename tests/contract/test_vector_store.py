"""One interface test suite for both VectorStore backends (CP4 deliverable 2).

The pgvector backend runs when a PostgreSQL server with the `vector` extension is reachable
at VULNTRACE_PG_DSN (default postgresql://postgres:postgres@localhost:5432/postgres) and
skips with a clear message otherwise. CI's pgvector job sets VULNTRACE_REQUIRE_PG=1, which
turns that skip into a failure, so a green CI job proves the tests really ran."""

import os
import uuid

import numpy as np
import pytest

from vulntrace.retrieval.vectorstore import InMemoryVectorStore, VectorRecord, VectorStoreError

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


def _pg_store():
    dsn = os.environ.get("VULNTRACE_PG_DSN", DEFAULT_DSN)
    reason = None
    try:
        from vulntrace.retrieval.pgvector_store import PgVectorStore

        store = PgVectorStore(dsn, table=f"vt_test_{uuid.uuid4().hex[:12]}", connect_timeout=3)
    except ImportError as exc:
        reason = f"psycopg/pgvector Python packages not installed ({exc})"
    except Exception as exc:  # connection refused, auth failure, extension missing, ...
        reason = f"no PostgreSQL + pgvector reachable at VULNTRACE_PG_DSN ({type(exc).__name__}: {str(exc)[:160]})"
    if reason is not None:
        if os.environ.get("VULNTRACE_REQUIRE_PG") == "1":
            pytest.fail(f"VULNTRACE_REQUIRE_PG=1 but {reason}")
        pytest.skip(f"SKIPPED pgvector backend: {reason}")
    return store


@pytest.fixture(params=["memory", "pgvector"])
def store(request):
    if request.param == "memory":
        yield InMemoryVectorStore()
        return
    s = _pg_store()
    try:
        yield s
    finally:
        s.drop_table()
        s.close()


def rec(chunk_id, vec, variant="code_only", model="m1", range_key="R1", **meta):
    return VectorRecord(chunk_id, np.asarray(vec, dtype=np.float32),
                        {"variant": variant, "embedding_model": model, "range_key": range_key, **meta})


def test_search_orders_by_cosine_similarity(store):
    store.upsert([rec("a", [1, 0, 0]), rec("b", [1, 1, 0]), rec("c", [0, 0, 1])])
    hits = store.search(np.array([1, 0.1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=3)
    assert [h.chunk_id for h in hits] == ["a", "b", "c"]
    assert hits[0].score == pytest.approx(1 / np.sqrt(1.01), abs=1e-5)
    assert hits[1].score == pytest.approx(1.1 / (np.sqrt(2) * np.sqrt(1.01)), abs=1e-5)
    assert hits[2].score == pytest.approx(0.0, abs=1e-5)


def test_cosine_ignores_vector_length(store):
    store.upsert([rec("long", [10, 0]), rec("short", [0.1, 0.1])])
    hits = store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=2)
    assert [h.chunk_id for h in hits] == ["long", "short"]
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)


def test_ties_are_ordered_by_chunk_id(store):
    store.upsert([rec("z", [1, 0]), rec("m", [1, 0]), rec("a", [1, 0])])
    hits = store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=3)
    assert [h.chunk_id for h in hits] == ["a", "m", "z"]


def test_k_limits_results(store):
    store.upsert([rec(f"c{i}", [1, i]) for i in range(5)])
    assert len(store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=2)) == 2
    assert store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=0) == []


def test_filters_scope_the_search(store):
    store.upsert([rec("a", [1, 0], range_key="R1"), rec("b", [1, 0], range_key="R2"),
                  rec("a", [0, 1], variant="code+commits", range_key="R1"),
                  rec("a", [1, 0, 0], model="m2", range_key="R1")])
    hits = store.search(np.array([1, 0], dtype=np.float32),
                        {"embedding_model": "m1", "variant": "code_only", "range_key": "R2"}, k=10)
    assert [(h.chunk_id, h.metadata["range_key"]) for h in hits] == [("b", "R2")]
    hits = store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1", "range_key": "R1"}, k=10)
    assert [(h.chunk_id, h.metadata["variant"]) for h in hits] == [("a", "code_only"), ("a", "code+commits")]
    assert store.search(np.array([1, 0, 0], dtype=np.float32), {"embedding_model": "m2"}, k=5)[0].chunk_id == "a"
    assert store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "nope"}, k=5) == []


def test_upsert_replaces_same_identity(store):
    store.upsert([rec("a", [1, 0], symbol="Old")])
    store.upsert([rec("a", [0, 1], symbol="New")])
    assert store.count({"embedding_model": "m1"}) == 1
    hits = store.search(np.array([0, 1], dtype=np.float32), {"embedding_model": "m1"}, k=1)
    assert hits[0].score == pytest.approx(1.0, abs=1e-5) and hits[0].metadata["symbol"] == "New"
    assert store.search(np.array([0, 1], dtype=np.float32), {"embedding_model": "m1", "symbol": "Old"}, k=1) == []


def test_metadata_round_trips(store):
    store.upsert([rec("a", [1, 0], package="p/q", symbol="T.M", candidate_id="r7", content_sha256="ab",
                      module="example.com/m", version="1.2.3")])
    h = store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1"}, k=1)[0]
    assert h.metadata == {"variant": "code_only", "embedding_model": "m1", "range_key": "R1", "package": "p/q",
                          "symbol": "T.M", "candidate_id": "r7", "content_sha256": "ab",
                          "module": "example.com/m", "version": "1.2.3"}


def test_delete_by_filter_returns_count(store):
    store.upsert([rec("a", [1, 0], range_key="R1"), rec("b", [1, 0], range_key="R1"),
                  rec("c", [1, 0], range_key="R2")])
    assert store.delete({"range_key": "R1"}) == 2
    assert store.count() == 1
    assert store.delete({"range_key": "R1"}) == 0


def test_contract_errors(store):
    store.upsert([rec("a", [1, 0])])
    with pytest.raises(VectorStoreError):
        store.search(np.array([1, 0], dtype=np.float32), {}, k=1)            # no embedding_model filter
    with pytest.raises(VectorStoreError):
        store.search(np.array([1, 0], dtype=np.float32), {"embedding_model": "m1", "bogus": "x"}, k=1)
    with pytest.raises(VectorStoreError):
        store.delete({})                                                       # refuses to delete everything
    with pytest.raises(VectorStoreError):
        store.upsert([VectorRecord("x", np.array([1.0, 0.0], dtype=np.float32), {"variant": "v"})])
    with pytest.raises(VectorStoreError):
        store.search(np.array([1, 0, 0], dtype=np.float32), {"embedding_model": "m1"}, k=1)  # wrong dimension
    assert store.count() == 1
