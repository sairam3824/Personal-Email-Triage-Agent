from __future__ import annotations

import base64
import random
import re
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from .models import EmailFull, EmailSummary

GMAIL_SCOPE = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailClient:
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        *,
        service: Any | None = None,
        dry_run: bool = False,
        user_id: str = "me",
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = service
        self.dry_run = dry_run
        self.user_id = user_id
        self._label_cache: dict[str, str] = {}

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _build_service(self) -> Any:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google API dependencies are missing. Install project dependencies first."
            ) from exc

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), GMAIL_SCOPE)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), GMAIL_SCOPE
                )
                creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds)

    def get_unread_emails(self, limit: int = 25) -> list[EmailSummary]:
        response = (
            self.service.users()
            .messages()
            .list(userId=self.user_id, labelIds=["INBOX", "UNREAD"], maxResults=limit)
            .execute()
        )
        messages = response.get("messages", [])
        results: list[EmailSummary] = []
        for item in messages:
            metadata = (
                self.service.users()
                .messages()
                .get(
                    userId=self.user_id,
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
            headers = self._headers_dict(metadata.get("payload", {}).get("headers", []))
            results.append(
                EmailSummary(
                    id=metadata["id"],
                    sender=headers.get("From", ""),
                    subject=headers.get("Subject", "(no subject)"),
                    body_preview=metadata.get("snippet", ""),
                    date=headers.get("Date", ""),
                )
            )
        return results

    def get_email_full(self, email_id: str) -> EmailFull:
        payload = (
            self.service.users()
            .messages()
            .get(userId=self.user_id, id=email_id, format="full")
            .execute()
        )
        headers = self._headers_dict(payload.get("payload", {}).get("headers", []))
        return EmailFull(
            id=payload["id"],
            sender=headers.get("From", ""),
            subject=headers.get("Subject", "(no subject)"),
            body_preview=payload.get("snippet", ""),
            date=headers.get("Date", ""),
            body_text=self._extract_body(payload.get("payload", {})),
            thread_id=payload.get("threadId"),
            list_unsubscribe=headers.get("List-Unsubscribe"),
            headers=headers,
        )

    def get_voice_samples(self, sample_size: int = 5) -> list[dict[str, str]]:
        response = (
            self.service.users()
            .messages()
            .list(userId=self.user_id, labelIds=["SENT"], maxResults=25)
            .execute()
        )
        messages = response.get("messages", [])
        selected = random.sample(messages, k=min(sample_size, len(messages)))
        samples: list[dict[str, str]] = []
        for item in selected:
            payload = (
                self.service.users()
                .messages()
                .get(userId=self.user_id, id=item["id"], format="full")
                .execute()
            )
            headers = self._headers_dict(payload.get("payload", {}).get("headers", []))
            samples.append(
                {
                    "subject": headers.get("Subject", "(no subject)"),
                    "body": self._extract_body(payload.get("payload", {})),
                }
            )
        return samples

    def draft_reply(self, email_id: str, body: str) -> dict[str, Any]:
        original = self.get_email_full(email_id)
        recipient = parseaddr(original.sender)[1] or original.sender
        subject = original.subject if original.subject.lower().startswith("re:") else f"Re: {original.subject}"

        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        if original.headers.get("Message-Id"):
            message["In-Reply-To"] = original.headers["Message-Id"]
            message["References"] = original.headers["Message-Id"]
        message.set_content(body)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        if self.dry_run:
            return {
                "status": "dry-run",
                "email_id": email_id,
                "draft_subject": subject,
                "draft_body": body,
            }

        draft = (
            self.service.users()
            .drafts()
            .create(
                userId=self.user_id,
                body={"message": {"threadId": original.thread_id, "raw": encoded}},
            )
            .execute()
        )
        return {"status": "created", "email_id": email_id, "draft_id": draft.get("id")}

    def apply_label(self, email_id: str, label_name: str) -> dict[str, Any]:
        if self.dry_run:
            return {"status": "dry-run", "email_id": email_id, "label": label_name}
        label_id = self._get_or_create_label(label_name)

        (
            self.service.users()
            .messages()
            .modify(userId=self.user_id, id=email_id, body={"addLabelIds": [label_id]})
            .execute()
        )
        return {"status": "applied", "email_id": email_id, "label": label_name}

    def archive(self, email_id: str) -> dict[str, Any]:
        if self.dry_run:
            return {"status": "dry-run", "email_id": email_id, "action": "archive"}
        (
            self.service.users()
            .messages()
            .modify(userId=self.user_id, id=email_id, body={"removeLabelIds": ["INBOX"]})
            .execute()
        )
        return {"status": "archived", "email_id": email_id}

    def trash(self, email_id: str) -> dict[str, Any]:
        if self.dry_run:
            return {"status": "dry-run", "email_id": email_id, "action": "trash"}
        self.service.users().messages().trash(userId=self.user_id, id=email_id).execute()
        return {"status": "trashed", "email_id": email_id}

    def _get_or_create_label(self, label_name: str) -> str:
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        response = self.service.users().labels().list(userId=self.user_id).execute()
        labels = response.get("labels", [])
        for label in labels:
            self._label_cache[label["name"]] = label["id"]
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        created = (
            self.service.users()
            .labels()
            .create(
                userId=self.user_id,
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_cache[label_name] = created["id"]
        return created["id"]

    @staticmethod
    def _headers_dict(headers: list[dict[str, str]]) -> dict[str, str]:
        return {header["name"]: header["value"] for header in headers if "name" in header}

    @classmethod
    def _extract_body(cls, payload: dict[str, Any]) -> str:
        mime_type = payload.get("mimeType", "")
        body = payload.get("body", {})
        data = body.get("data")

        if mime_type == "text/plain" and data:
            return cls._decode_body_data(data)

        parts = payload.get("parts", [])
        for part in parts:
            text = cls._extract_body(part)
            if text:
                return text

        if data:
            decoded = cls._decode_body_data(data)
            if mime_type == "text/html":
                return cls._strip_html(decoded)
            return decoded
        return ""

    @staticmethod
    def _decode_body_data(data: str) -> str:
        padding = "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode((data + padding).encode("utf-8"))
        return decoded.decode("utf-8", errors="replace")

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
