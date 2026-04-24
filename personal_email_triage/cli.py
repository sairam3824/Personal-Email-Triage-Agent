from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .audit import AuditStore
from .config import Settings
from .gmail_client import GmailClient
from .service import TriageService
from .agent import OpenAITriageAgent
from .rules import RulesStore
from .unsubscribe import UnsubscribeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal email triage agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the inbox triage once.")
    run_parser.add_argument("--dry", action="store_true", help="Print actions without mutating Gmail.")
    run_parser.add_argument("--limit", type=int, default=None, help="Maximum unread emails to process.")

    daemon_parser = subparsers.add_parser("daemon", help="Run the scheduler every 15 minutes.")
    daemon_parser.add_argument("--dry", action="store_true", help="Run the scheduler in dry mode.")
    daemon_parser.add_argument("--limit", type=int, default=None, help="Maximum unread emails per cycle.")

    feedback_parser = subparsers.add_parser(
        "feedback", help="Teach the agent a corrected category for an email."
    )
    feedback_parser.add_argument("email_id")
    feedback_parser.add_argument("correct_category")
    return parser


def create_service(settings: Settings, *, dry_run: bool) -> TriageService:
    gmail_client = GmailClient(
        settings.gmail_credentials_path,
        settings.gmail_token_path,
        dry_run=dry_run,
    )
    rules_store = RulesStore(settings.rules_path)
    audit_store = AuditStore(settings.sqlite_path)
    agent = OpenAITriageAgent(settings.openai_api_key, settings.openai_model)
    unsubscribe_service = UnsubscribeService(dry_run=dry_run)
    return TriageService(
        gmail_client,
        rules_store,
        audit_store,
        agent,
        unsubscribe_service,
        dry_run=dry_run,
    )


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env(Path.cwd())

    if args.command in {"run", "daemon"}:
        settings.validate_for_runtime()
        service = create_service(settings, dry_run=args.dry)
        limit = args.limit or settings.triage_limit
        if args.command == "run":
            result = service.triage_inbox(limit=limit)
            print(json.dumps(result, indent=2))
            return

        service.run_daemon(limit=limit)
        return

    service = create_service(settings, dry_run=False)
    learned_rule = service.learn_from_feedback(args.email_id, args.correct_category)
    print(learned_rule)


if __name__ == "__main__":
    main()
