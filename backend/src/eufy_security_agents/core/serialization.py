"""Stable JSON serialization for agent prompts."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def compact_json(value: Any) -> str:
    def encode(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=encode,
    )
