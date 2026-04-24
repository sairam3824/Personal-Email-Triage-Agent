from __future__ import annotations

from pathlib import Path

from personal_email_triage.audit import AuditStore
from personal_email_triage.models import EmailFull
from personal_email_triage.rules import RulesStore
from personal_email_triage.service import TriageService
from personal_email_triage.unsubscribe import UnsubscribeService


class FeedbackOnlyAgent:
    def triage(self, tool_executor, limit: int):
        raise AssertionError("This test should not call triage().")


class FeedbackGmailClient:
    def get_email_full(self, email_id: str):
        return EmailFull(
            id=email_id,
            sender="notifications@github.com",
            subject="New mention",
            body_preview="Preview",
            date="Thu, 23 Apr 2026 10:00:00 +0000",
            body_text="Body",
        )


def test_feedback_appends_rule_and_records_it(tmp_path: Path):
    audit_store = AuditStore(tmp_path / "triage.db")
    rules_store = RulesStore(tmp_path / "rules.md")
    service = TriageService(
        FeedbackGmailClient(),
        rules_store,
        audit_store,
        FeedbackOnlyAgent(),
        UnsubscribeService(dry_run=True),
    )

    rule_entry = service.learn_from_feedback("email-123", "archive")

    assert "notifications@github.com" in rule_entry
    assert "archive" in rules_store.read_rules()
