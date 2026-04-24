# Personal Email Triage Agent

A production-oriented Python CLI for Gmail inbox triage. The agent reads unread Gmail messages, classifies each item, drafts replies, archives low-priority mail, handles unsubscribe flows, and learns from feedback through a local rules file.

The project is designed to run locally, keep operational records in SQLite, and start in dry-run mode so behavior can be reviewed before Gmail is modified.

## Features

- Gmail OAuth support using the `gmail.modify` scope
- OpenAI-powered classification and reply drafting
- One-shot triage and 15-minute daemon modes
- Dry-run mode for safe inspection
- Gmail labels in the format `TRIAGE/<category>`
- Categories: `respond-now`, `respond-later`, `delegate`, `archive`, `unsubscribe`
- Local preference learning through `rules.md`
- SQLite audit log for triage decisions and feedback
- Playwright-based unsubscribe automation
- Unit tests with mocked Gmail clients

## Requirements

- Python 3.11 or newer
- OpenAI API key
- Google Cloud project with Gmail API enabled
- Gmail OAuth desktop credentials JSON

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
playwright install chromium
cp .env.example .env
```

Edit `.env`, add your `OPENAI_API_KEY`, and place your Gmail OAuth file at `credentials.json`.

Run a safe dry run:

```bash
triage run --dry --limit 10
```

Run and apply Gmail actions:

```bash
triage run
```

## Gmail OAuth Setup

1. Create or select a Google Cloud project.
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID with application type `Desktop app`.
5. Download the JSON credentials file.
6. Save it as `credentials.json`, or set `GMAIL_CREDENTIALS_PATH` in `.env`.

On the first run, the app opens a browser for Gmail authorization and stores the refreshable token at `GMAIL_TOKEN_PATH`.

## Configuration

The app reads configuration from environment variables. A local `.env` file is loaded automatically.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
GMAIL_CREDENTIALS_PATH=./credentials.json
GMAIL_TOKEN_PATH=./token.json
RULES_PATH=./rules.md
TRIAGE_DB_PATH=./triage.db
TRIAGE_LIMIT=25
```

| Variable | Description | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API key used by the triage agent | Required |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4.1-mini` |
| `GMAIL_CREDENTIALS_PATH` | Path to Gmail OAuth desktop credentials | `./credentials.json` |
| `GMAIL_TOKEN_PATH` | Path where the Gmail token is stored | `./token.json` |
| `RULES_PATH` | Local learned preference rules file | `./rules.md` |
| `TRIAGE_DB_PATH` | SQLite audit database path | `./triage.db` |
| `TRIAGE_LIMIT` | Default unread email limit per run | `25` |

## Usage

Run once without changing Gmail:

```bash
triage run --dry --limit 10
```

Run once and apply actions:

```bash
triage run
```

Run continuously every 15 minutes:

```bash
triage daemon
```

Run the daemon in dry-run mode:

```bash
triage daemon --dry --limit 10
```

Teach the agent a corrected category:

```bash
triage feedback EMAIL_ID archive
```

Supported feedback categories are `respond-now`, `respond-later`, `delegate`, `archive`, and `unsubscribe`.

## How It Works

1. Fetch unread Gmail messages.
2. Read learned preferences from `rules.md`.
3. Use OpenAI to classify each message and prepare required actions.
4. Apply Gmail labels and actions, unless dry-run mode is enabled.
5. Store every decision in the local SQLite audit log.
6. Append future preferences when feedback is provided.

## Project Structure

```text
personal_email_triage/
  agent.py          OpenAI tool loop and decision collection
  audit.py          SQLite audit log
  cli.py            Command-line entrypoint
  config.py         Environment-based settings
  gmail_client.py   Gmail API client
  models.py         Data models
  rules.py          Learned preference store
  service.py        Triage orchestration
  unsubscribe.py    Unsubscribe automation
tests/              Unit tests
docs/               CLI screenshots
rules.md            Local learned rules
torun.txt           Minimal run commands
```

## Testing

```bash
pytest
```

Tests use mocked Gmail clients and temporary files, so real Gmail credentials are not required.

## Production Notes

- Start with `--dry` before allowing Gmail changes.
- Keep `.env`, `credentials.json`, `token.json`, and `triage.db` out of version control.
- Run the daemon under a process manager if deploying on a server.
- Back up `rules.md` and `triage.db` if you rely on learned preferences or audit history.
- Rotate OAuth credentials and API keys if they are exposed.
- Review OpenAI and Google data policies before using the agent with sensitive mailboxes.

## Security

This project can read and modify Gmail messages after OAuth authorization. Treat local credentials and tokens as secrets. The agent may send email content to OpenAI for classification and drafting, depending on the action being performed.

If you discover a security issue, revoke the affected Gmail token and OpenAI key first, then patch or rotate credentials before running the agent again.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
