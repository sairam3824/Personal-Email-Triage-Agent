from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RULES = """# Learned Triage Rules

The agent appends lightweight preference rules here as you correct decisions.
Keep rules short, concrete, and easy to generalize.
"""


class RulesStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text(DEFAULT_RULES, encoding="utf-8")

    def read_rules(self) -> str:
        self._ensure_file()
        return self.path.read_text(encoding="utf-8")

    def append_rule(self, text: str) -> str:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Rule text must not be empty.")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"- [{timestamp}] {clean_text}\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return entry.strip()
