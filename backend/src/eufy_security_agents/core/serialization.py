"""Stable JSON serialization for agent prompts."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def compact_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value
        ]
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
