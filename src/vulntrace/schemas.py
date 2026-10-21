"""JSON Schema validation helpers. Requires the `jsonschema` package."""

import json
from pathlib import Path

from vulntrace.paths import SCHEMAS_DIR

SCHEMA_VERSION = "1.0"

_FILES = {
    "fixture_manifest": "fixture_manifest.schema.json",
    "method_result": "method_result.schema.json",
}


def load_schema(name: str, schemas_dir: Path = SCHEMAS_DIR) -> dict:
    return json.loads((Path(schemas_dir) / _FILES[name]).read_text(encoding="utf-8"))


def validation_errors(name: str, instance: object) -> list[str]:
    """Return human-readable schema violations (empty list means valid)."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(load_schema(name))
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    ]


def validate(name: str, instance: object) -> None:
    errors = validation_errors(name, instance)
    if errors:
        raise ValueError(f"{name} validation failed: " + "; ".join(errors))
