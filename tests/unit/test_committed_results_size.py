"""Size limits for committed result files (set in CP4, PROJECT_STRUCTURE.md): small reviewed
summaries only. Each file under docs/results/ at most 512 KiB; docs/results/cp4/ at most 2 MiB."""

from vulntrace.paths import REPO_ROOT

RESULTS = REPO_ROOT / "docs" / "results"
MAX_FILE = 512 * 1024
MAX_CP4_TOTAL = 2 * 1024 * 1024


def test_each_committed_result_file_is_small():
    for p in RESULTS.rglob("*"):
        if p.is_file():
            assert p.stat().st_size <= MAX_FILE, f"{p} is {p.stat().st_size} bytes"


def test_cp4_result_bundle_is_small_and_json_only():
    cp4 = RESULTS / "cp4"
    files = [p for p in cp4.rglob("*") if p.is_file()] if cp4.is_dir() else []
    assert sum(p.stat().st_size for p in files) <= MAX_CP4_TOTAL
    assert all(p.suffix == ".json" for p in files)
