from __future__ import annotations

import base64

from personal_email_triage.gmail_client import GmailClient


def encode_body(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeMessagesApi:
    def __init__(self) -> None:
        self.modified = []
        self.trashed = []
        self.metadata_messages = {
            "msg-1": {
                "id": "msg-1",
                "snippet": "Schedule a project sync tomorrow",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Alice <alice@example.com>"},
                        {"name": "Subject", "value": "Quick sync"},
                        {"name": "Date", "value": "Thu, 23 Apr 2026 10:00:00 +0000"},
                    ]
                },
            }
        }
        self.full_messages = {
            "msg-1": {
                "id": "msg-1",
                "threadId": "thread-1",
                "snippet": "Schedule a project sync tomorrow",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [
                        {"name": "From", "value": "Alice <alice@example.com>"},
                        {"name": "Subject", "value": "Quick sync"},
                        {"name": "Date", "value": "Thu, 23 Apr 2026 10:00:00 +0000"},
                        {"name": "Message-Id", "value": "<message-1@example.com>"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": encode_body("Can we talk tomorrow?")},
                        }
                    ],
                },
            },
            "sent-1": {
                "id": "sent-1",
                "threadId": "thread-2",
                "snippet": "Absolutely, that works.",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": "Re: Planning"}],
                    "body": {"data": encode_body("Absolutely, that works for me.")},
                },
            },
        }

    def list(self, *, userId, labelIds, maxResults):
        if labelIds == ["INBOX", "UNREAD"]:
            return FakeRequest({"messages": [{"id": "msg-1"}]})
        if labelIds == ["SENT"]:
            return FakeRequest({"messages": [{"id": "sent-1"}]})
        return FakeRequest({"messages": []})

    def get(self, *, userId, id, format, metadataHeaders=None):
        if format == "metadata":
            return FakeRequest(self.metadata_messages[id])
        return FakeRequest(self.full_messages[id])

    def modify(self, *, userId, id, body):
        self.modified.append({"id": id, "body": body})
        return FakeRequest({"id": id, "body": body})

    def trash(self, *, userId, id):
        self.trashed.append(id)
        return FakeRequest({"id": id})


class FakeDraftsApi:
    def __init__(self) -> None:
        self.created = []

    def create(self, *, userId, body):
        self.created.append(body)
        return FakeRequest({"id": "draft-1"})


class FakeLabelsApi:
    def __init__(self) -> None:
        self.created = []

    def list(self, *, userId):
        return FakeRequest({"labels": [{"id": "LBL_EXISTING", "name": "Inbox"}]})

    def create(self, *, userId, body):
        self.created.append(body)
        return FakeRequest({"id": "LBL_TRIAGE", "name": body["name"]})


class FakeUsersApi:
    def __init__(self) -> None:
        self._messages = FakeMessagesApi()
        self._drafts = FakeDraftsApi()
        self._labels = FakeLabelsApi()

    def messages(self):
        return self._messages

    def drafts(self):
        return self._drafts

    def labels(self):
        return self._labels


class FakeService:
    def __init__(self) -> None:
        self._users = FakeUsersApi()

    def users(self):
        return self._users


def test_get_unread_emails_returns_summaries(tmp_path):
    client = GmailClient(tmp_path / "credentials.json", tmp_path / "token.json", service=FakeService())

    unread = client.get_unread_emails(limit=10)

    assert len(unread) == 1
    assert unread[0].id == "msg-1"
    assert unread[0].sender == "Alice <alice@example.com>"
    assert unread[0].subject == "Quick sync"


def test_apply_label_creates_missing_label_and_modifies_message(tmp_path):
    service = FakeService()
    client = GmailClient(tmp_path / "credentials.json", tmp_path / "token.json", service=service)

    result = client.apply_label("msg-1", "TRIAGE/respond-now")

    assert result["status"] == "applied"
    assert service.users().labels().created[0]["name"] == "TRIAGE/respond-now"
    assert service.users().messages().modified[0]["body"] == {"addLabelIds": ["LBL_TRIAGE"]}


def test_draft_reply_creates_gmail_draft(tmp_path):
    service = FakeService()
    client = GmailClient(tmp_path / "credentials.json", tmp_path / "token.json", service=service)

    result = client.draft_reply("msg-1", "Tomorrow works for me.")

    assert result["status"] == "created"
    created = service.users().drafts().created[0]
    assert created["message"]["threadId"] == "thread-1"
