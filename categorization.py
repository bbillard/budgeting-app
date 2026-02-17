from __future__ import annotations

import json
from pathlib import Path

RULES_PATH = Path("categorization_rules.json")
DEFAULT_CATEGORY = "À catégoriser"


def load_rules() -> dict[str, str]:
    if not RULES_PATH.exists():
        return {}
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def infer_category(description: str) -> str:
    rules = load_rules()
    value = description.lower()
    for keyword, category in rules.items():
        if keyword.lower() in value:
            return category
    return DEFAULT_CATEGORY
