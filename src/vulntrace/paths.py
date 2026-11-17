"""Locations of repository files (source-tree layout)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
FIXTURES_DIR = REPO_ROOT / "fixtures" / "reachability"
# CP9: path-feasibility fixtures (module vtfeas), separate so the CP2/CP7 suite stays unchanged
FEASIBILITY_FIXTURES_DIR = REPO_ROOT / "fixtures" / "feasibility"
