from __future__ import annotations

import json
from typing import Any

from .models import DecisionRecord, EmailFull, EmailSummary


SYSTEM_PROMPT = """You are a careful personal inbox triage agent.

Use tools to fetch unread messages, full email content, five sent-email voice samples, and the learned rules file.
Classify each unread email into exactly one category:
- respond-now: deserves a reply within 24 hours
- respond-later: deserves a reply within one week
- delegate: should be handled by someone else; include a short delegation suggestion
- archive: informational and no response needed
- unsubscribe: newsletter or recurring promo content that should be unsubscribed from

Behavior rules:
1. Always consult the learned rules before deciding.
2. For respond-now and respond-later, draft a reply in the user's voice before completing the run.
3. Always apply a Gmail label in the form TRIAGE/<category>.
4. For archive, archive the message.
5. For unsubscribe, apply the label and call unsubscribe.
6. Keep reasoning concise and audit-friendly.
7. Finish by calling complete_run with every processed email.
"""


class AgentToolExecutor:
    def __init__(self, gmail_client: Any, rules_store: Any, unsubscribe_service: Any) -> None:
        self.gmail_client = gmail_client
        self.rules_store = rules_store
        self.unsubscribe_service = unsubscribe_service
        self.email_cache: dict[str, EmailFull] = {}
        self.summary_cache: dict[str, EmailSummary] = {}
        self.actions: dict[str, list[dict[str, Any]]] = {}
        self.decisions: list[DecisionRecord] = []

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "get_unread_emails",
                "description": "Fetch unread inbox emails.",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                    "required": ["limit"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_email_full",
                "description": "Fetch the full text of an email.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_voice_samples",
                "description": "Fetch five random sent emails as voice samples.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "draft_reply",
                "description": "Create a Gmail draft reply for an email.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["id", "body"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "apply_label",
                "description": "Apply a Gmail label such as TRIAGE/respond-now.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
                    "required": ["id", "label"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "archive",
                "description": "Archive an email by removing the inbox label.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "trash",
                "description": "Move an email to trash.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "unsubscribe",
                "description": "Unsubscribe from a mailing list using the message headers or body.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "read_rules",
                "description": "Read the learned rules file.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "append_rule",
                "description": "Append a short learned preference rule to the rules file.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "complete_run",
                "description": "Submit the final triage decisions for every processed email.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "decisions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email_id": {"type": "string"},
                                    "category": {
                                        "type": "string",
                                        "enum": [
                                            "respond-now",
                                            "respond-later",
                                            "delegate",
                                            "archive",
                                            "unsubscribe",
                                        ],
                                    },
                                    "reasoning_trace": {"type": "string"},
                                    "sender": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "reply_body": {"type": "string"},
                                    "delegate_note": {"type": "string"},
                                    "learned_rule": {"type": "string"},
                                },
                                "required": [
                                    "email_id",
                                    "category",
                                    "reasoning_trace",
                                    "sender",
                                    "subject",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["decisions"],
                    "additionalProperties": False,
                },
            },
        ]

    def invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        method = getattr(self, name)
        return method(**args)

    def get_unread_emails(self, limit: int) -> dict[str, Any]:
        emails = self.gmail_client.get_unread_emails(limit=limit)
        for email in emails:
            self.summary_cache[email.id] = email
        return {"emails": [email.to_dict() for email in emails]}

    def get_email_full(self, id: str) -> dict[str, Any]:
        email = self.gmail_client.get_email_full(id)
        self.email_cache[id] = email
        return email.to_dict()

    def get_voice_samples(self) -> dict[str, Any]:
        return {"samples": self.gmail_client.get_voice_samples()}

    def draft_reply(self, id: str, body: str) -> dict[str, Any]:
        result = self.gmail_client.draft_reply(id, body)
        self._record_action(id, "draft_reply", result | {"body": body})
        return result

    def apply_label(self, id: str, label: str) -> dict[str, Any]:
        result = self.gmail_client.apply_label(id, label)
        self._record_action(id, "apply_label", result | {"label": label})
        return result

    def archive(self, id: str) -> dict[str, Any]:
        result = self.gmail_client.archive(id)
        self._record_action(id, "archive", result)
        return result

    def trash(self, id: str) -> dict[str, Any]:
        result = self.gmail_client.trash(id)
        self._record_action(id, "trash", result)
        return result

    def unsubscribe(self, id: str) -> dict[str, Any]:
        email = self.email_cache.get(id) or self.gmail_client.get_email_full(id)
        self.email_cache[id] = email
        result = self.unsubscribe_service.unsubscribe(email)
        self._record_action(id, "unsubscribe", result)
        return result

    def read_rules(self) -> dict[str, Any]:
        return {"rules": self.rules_store.read_rules()}

    def append_rule(self, text: str) -> dict[str, Any]:
        result = self.rules_store.append_rule(text)
        return {"entry": result}

    def complete_run(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        self.decisions = [DecisionRecord.from_dict(item) for item in decisions]
        for record in self.decisions:
            record.actions = list(self.actions.get(record.email_id, []))
        return {"accepted": True, "count": len(self.decisions)}

    def _record_action(self, email_id: str, action_type: str, payload: dict[str, Any]) -> None:
        self.actions.setdefault(email_id, []).append({"type": action_type, "payload": payload})


class OpenAITriageAgent:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def triage(self, tool_executor: AgentToolExecutor, limit: int) -> list[DecisionRecord]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed. Install project dependencies first.") from exc

        client = OpenAI(api_key=self.api_key)
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Triage the unread inbox now. Process up to {limit} unread emails.",
                },
            ],
            tools=tool_executor.tool_schemas(),
        )

        while True:
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                break

            tool_outputs = []
            for item in function_calls:
                arguments = json.loads(item.arguments or "{}")
                result = tool_executor.invoke(item.name, arguments)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps(result, ensure_ascii=True),
                    }
                )

            response = client.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=tool_executor.tool_schemas(),
            )

        if tool_executor.decisions:
            return tool_executor.decisions

        raw_output = (response.output_text or "").strip()
        if not raw_output:
            raise RuntimeError("Model returned no decisions.")
        data = json.loads(raw_output)
        decisions = [DecisionRecord.from_dict(item) for item in data]
        for record in decisions:
            record.actions = list(tool_executor.actions.get(record.email_id, []))
        return decisions
