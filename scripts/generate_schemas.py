"""Generate JSON Schemas for MCP tool inputs and outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import json

from pydantic import BaseModel

from meta_mcp.meta_client import models

SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schemas"
INPUT_DIR = SCHEMA_ROOT / "inputs"
OUTPUT_DIR = SCHEMA_ROOT / "responses"


def iter_models() -> Iterable[tuple[str, type[BaseModel]]]:
    for name in models.__all__:
        attr = getattr(models, name)
        if isinstance(attr, type) and issubclass(attr, BaseModel):
            yield name, attr


def write_schema(name: str, model: type[BaseModel], folder: Path) -> None:
    schema = model.model_json_schema(mode="validation")
    path = folder / f"{name}.json"
    path.write_text(json.dumps(schema, indent=2, sort_keys=True))


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in iter_models():
        if name.endswith("Request") or name.endswith("Input") or name.endswith("List") or name.endswith("Create") or name.endswith("Update"):
            write_schema(name, model, INPUT_DIR)
        elif name.endswith("Response") or name.endswith("Output"):
            write_schema(name, model, OUTPUT_DIR)


if __name__ == "__main__":
    main()
