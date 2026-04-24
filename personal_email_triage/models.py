from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CATEGORIES = {
    "respond-now",
    "respond-later",
    "delegate",
    "archive",
    "unsubscribe",
}


@dataclass(slots=True)
class EmailSummary:
    id: str
    sender: str
    subject: str
    body_preview: str
    date: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class EmailFull:
    id: str
    sender: str
    subject: str
    body_preview: str
    date: str
    body_text: str
    thread_id: str | None = None
    list_unsubscribe: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DecisionRecord:
    email_id: str
    category: str
    reasoning_trace: str
    sender: str
    subject: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    reply_body: str | None = None
    delegate_note: str | None = None
    learned_rule: str | None = None

    def validate(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"Unsupported category: {self.category}")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionRecord":
        record = cls(
            email_id=str(payload["email_id"]),
            category=str(payload["category"]),
            reasoning_trace=str(payload["reasoning_trace"]),
            sender=str(payload.get("sender", "")),
            subject=str(payload.get("subject", "")),
            actions=list(payload.get("actions", [])),
            reply_body=payload.get("reply_body"),
            delegate_note=payload.get("delegate_note"),
            learned_rule=payload.get("learned_rule"),
        )
        record.validate()
        return record
