from __future__ import annotations

import re
from typing import Any

from .models import EmailFull

URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")


class UnsubscribeService:
    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def unsubscribe(self, email: EmailFull) -> dict[str, Any]:
        target = self.find_target(email)
        if not target:
            return {"status": "no-link-found", "email_id": email.id}
        if self.dry_run:
            return {"status": "dry-run", "email_id": email.id, "target": target}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Install dependencies and run `playwright install`."
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(target, wait_until="networkidle", timeout=45_000)
            for label in (
                "text=Unsubscribe",
                "text=Yes, unsubscribe me",
                "text=Confirm",
                "text=Manage preferences",
            ):
                try:
                    locator = page.locator(label).first
                    if locator.count():
                        locator.click(timeout=5_000)
                        break
                except Exception:
                    continue
            final_url = page.url
            browser.close()
        return {"status": "completed", "email_id": email.id, "target": target, "final_url": final_url}

    def find_target(self, email: EmailFull) -> str | None:
        if email.list_unsubscribe:
            for token in [piece.strip(" <>") for piece in email.list_unsubscribe.split(",")]:
                if token.startswith("http://") or token.startswith("https://"):
                    return token
        match = URL_PATTERN.search(email.body_text)
        if match and "unsubscribe" in match.group(0).lower():
            return match.group(0)
        return None
