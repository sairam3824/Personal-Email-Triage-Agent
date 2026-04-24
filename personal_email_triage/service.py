from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from .agent import AgentToolExecutor, OpenAITriageAgent
from .audit import AuditStore
from .gmail_client import GmailClient
from .models import DecisionRecord
from .rules import RulesStore
from .unsubscribe import UnsubscribeService


class TriageService:
    def __init__(
        self,
        gmail_client: GmailClient,
        rules_store: RulesStore,
        audit_store: AuditStore,
        agent: OpenAITriageAgent,
        unsubscribe_service: UnsubscribeService,
        *,
        dry_run: bool = False,
    ) -> None:
        self.gmail_client = gmail_client
        self.rules_store = rules_store
        self.audit_store = audit_store
        self.agent = agent
        self.unsubscribe_service = unsubscribe_service
        self.dry_run = dry_run

    def triage_inbox(self, limit: int) -> dict[str, Any]:
        run_id = str(uuid4())
        executor = AgentToolExecutor(self.gmail_client, self.rules_store, self.unsubscribe_service)
        decisions = self.agent.triage(executor, limit=limit)
        normalized = [self._ensure_required_actions(decision) for decision in decisions]
        for decision in normalized:
            self.audit_store.log_decision(run_id, decision, self.dry_run)
        return {
            "run_id": run_id,
            "dry_run": self.dry_run,
            "processed": len(normalized),
            "decisions": [asdict(decision) for decision in normalized],
        }

    def learn_from_feedback(self, email_id: str, correct_category: str) -> str:
        if correct_category not in {"respond-now", "respond-later", "delegate", "archive", "unsubscribe"}:
            raise ValueError(f"Unsupported category: {correct_category}")

        metadata = self.audit_store.latest_email_metadata(email_id)
        if metadata is None:
            email = self.gmail_client.get_email_full(email_id)
            sender = email.sender
        else:
            sender = metadata["sender"]

        learned_rule = f"Emails from {sender} -> {correct_category}"
        entry = self.rules_store.append_rule(learned_rule)
        self.audit_store.log_feedback(email_id, correct_category, learned_rule)
        return entry

    def run_daemon(self, limit: int) -> None:
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
        except ImportError as exc:
            raise RuntimeError(
                "APScheduler is not installed. Install project dependencies first."
            ) from exc

        scheduler = BlockingScheduler()
        scheduler.add_job(self.triage_inbox, "interval", minutes=15, kwargs={"limit": limit})
        scheduler.start()

    def _ensure_required_actions(self, decision: DecisionRecord) -> DecisionRecord:
        decision.validate()
        labels = [action for action in decision.actions if action["type"] == "apply_label"]
        if not labels:
            label_result = self.gmail_client.apply_label(decision.email_id, f"TRIAGE/{decision.category}")
            decision.actions.append({"type": "apply_label", "payload": label_result})

        if decision.category in {"respond-now", "respond-later"}:
            has_draft = any(action["type"] == "draft_reply" for action in decision.actions)
            if not has_draft:
                body = decision.reply_body or "Thanks for the note. I will get back to you soon."
                draft_result = self.gmail_client.draft_reply(decision.email_id, body)
                decision.actions.append({"type": "draft_reply", "payload": draft_result | {"body": body}})

        if decision.category == "archive":
            has_archive = any(action["type"] == "archive" for action in decision.actions)
            if not has_archive:
                decision.actions.append(
                    {"type": "archive", "payload": self.gmail_client.archive(decision.email_id)}
                )

        if decision.category == "unsubscribe":
            has_unsubscribe = any(action["type"] == "unsubscribe" for action in decision.actions)
            if not has_unsubscribe:
                email = self.gmail_client.get_email_full(decision.email_id)
                result = self.unsubscribe_service.unsubscribe(email)
                decision.actions.append({"type": "unsubscribe", "payload": result})

        return decision
