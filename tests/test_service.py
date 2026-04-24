from __future__ import annotations

from pathlib import Path

from personal_email_triage.audit import AuditStore
from personal_email_triage.models import DecisionRecord, EmailFull
from personal_email_triage.rules import RulesStore
from personal_email_triage.service import TriageService
from personal_email_triage.unsubscribe import UnsubscribeService


class FakeGmailClient:
    def __init__(self) -> None:
        self.applied_labels = []
        self.drafts = []
        self.archives = []

    def apply_label(self, email_id: str, label_name: str):
        self.applied_labels.append((email_id, label_name))
        return {"status": "applied", "email_id": email_id, "label": label_name}

    def draft_reply(self, email_id: str, body: str):
        self.drafts.append((email_id, body))
        return {"status": "created", "email_id": email_id, "draft_id": "draft-1"}

    def archive(self, email_id: str):
        self.archives.append(email_id)
        return {"status": "archived", "email_id": email_id}

    def get_email_full(self, email_id: str):
        return EmailFull(
            id=email_id,
            sender="updates@example.com",
            subject="Status Update",
            body_preview="Status",
            date="Thu, 23 Apr 2026 10:00:00 +0000",
            body_text="Full body",
        )


class FakeAgent:
    def triage(self, tool_executor, limit: int):
        return [
            DecisionRecord(
                email_id="msg-1",
                category="respond-now",
                reasoning_trace="The sender is asking for a same-day scheduling confirmation.",
                sender="Alice <alice@example.com>",
                subject="Quick sync",
                reply_body="Tomorrow works for me. Happy to chat then.",
            ),
            DecisionRecord(
                email_id="msg-2",
                category="archive",
                reasoning_trace="This is informational and needs no reply.",
                sender="updates@example.com",
                subject="Status Update",
            ),
        ]


def test_triage_inbox_enforces_required_actions_and_logs(tmp_path: Path):
    audit_store = AuditStore(tmp_path / "triage.db")
    rules_store = RulesStore(tmp_path / "rules.md")
    gmail_client = FakeGmailClient()
    service = TriageService(
        gmail_client,
        rules_store,
        audit_store,
        FakeAgent(),
        UnsubscribeService(dry_run=True),
        dry_run=True,
    )

    result = service.triage_inbox(limit=10)

    assert result["processed"] == 2
    assert gmail_client.applied_labels == [
        ("msg-1", "TRIAGE/respond-now"),
        ("msg-2", "TRIAGE/archive"),
    ]
    assert gmail_client.drafts == [("msg-1", "Tomorrow works for me. Happy to chat then.")]
    assert gmail_client.archives == ["msg-2"]
    assert audit_store.latest_email_metadata("msg-1") == {
        "sender": "Alice <alice@example.com>",
        "subject": "Quick sync",
        "category": "respond-now",
    }
