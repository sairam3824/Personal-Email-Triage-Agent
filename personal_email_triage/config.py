from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    openai_api_key: str
    openai_model: str
    gmail_credentials_path: Path
    gmail_token_path: Path
    rules_path: Path
    sqlite_path: Path
    triage_limit: int

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Settings":
        base_dir = root or Path.cwd()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            gmail_credentials_path=Path(
                os.getenv("GMAIL_CREDENTIALS_PATH", str(base_dir / "credentials.json"))
            ),
            gmail_token_path=Path(os.getenv("GMAIL_TOKEN_PATH", str(base_dir / "token.json"))),
            rules_path=Path(os.getenv("RULES_PATH", str(base_dir / "rules.md"))),
            sqlite_path=Path(os.getenv("TRIAGE_DB_PATH", str(base_dir / "triage.db"))),
            triage_limit=int(os.getenv("TRIAGE_LIMIT", "25")),
        )

    def validate_for_runtime(self) -> None:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to run the triage agent.")
        if not self.gmail_credentials_path.exists():
            raise FileNotFoundError(
                f"Gmail OAuth credentials not found at {self.gmail_credentials_path}"
            )
