# Adrobot for Keitaro

A small web application for creating test campaigns and editing offer distribution through the Keitaro Admin API. The interface is in Russian; application logs and developer documentation are in English.

[![CI](https://github.com/lkmavi/adrobot-keitaro/actions/workflows/ci.yml/badge.svg)](https://github.com/lkmavi/adrobot-keitaro/actions/workflows/ci.yml)

## Features

- Create a campaign with a country-specific redirect and a fallback offer stream.
- Select existing domains, campaign groups, traffic sources, and offers, or create supported resources when the API credentials allow it.
- Edit stream offers as a local draft, pin traffic shares, restore archived offers, and publish changes explicitly.
- Detect upstream offer changes before publishing and verify the result after the update.
- Search structured application logs by service, level, module, and function in Grafana.

Keitaro is the source of truth for published campaigns. SQLite stores local drafts, pinned shares, and archived offer assignments. Traffic shares are whole percentages; any remainder is assigned deterministically in list order.

## Requirements

- Docker with Compose, for the application and local observability stack; or Python 3.12+ and [uv](https://docs.astral.sh/uv/) for local development.
- A Keitaro instance with Admin API access and credentials with the required permissions.
- Existing Keitaro resources for the campaign. Adding a domain to Keitaro does not register it or configure DNS.

## Quick start

```bash
cp .env.example .env
# Edit .env and set KEITARO_URL and KEITARO_API_KEY.
make docker-up
```

Open [the application](http://127.0.0.1:8000). The first build also starts Loki, Alloy, and Grafana. Open the [log dashboard](http://127.0.0.1:3300/d/adrobot-logs/adrobot?from=now-24h&to=now&refresh=10s) or use **Журнал событий** in the application.

Stop the stack with `make docker-down`. Named Docker volumes retain application data and logs. Do not use `docker compose down -v` unless you intend to delete those volumes.

For local development without the observability stack:

```bash
cp .env.example .env
# Set your API settings and DATABASE_PATH=./adrobot.sqlite3 in .env.
make install
make run
```

Never commit `.env` or share an API key. Use a dedicated test instance and test resources when experimenting with campaign creation.

## Configuration

| Variable | Purpose | Example |
| --- | --- | --- |
| `KEITARO_URL` | Base URL of the tracker | `https://tracker.example` |
| `KEITARO_API_KEY` | Server-side Admin API key | Set locally in `.env` |
| `CAMPAIGN_PREFIX` | Prefix for new test campaigns and groups | `test_lkmavi_` |
| `DATABASE_PATH` | Path to the local SQLite database | `./adrobot.sqlite3` |
| `OFFER_CREATION_ENABLED` | Hide and block offer creation when access is known to be unavailable | `false` |
| `REDIRECT_URL` | Destination for the country-filtered stream | `https://www.google.com/` |
| `KEITARO_TIMEOUT` | API request timeout, in seconds | `20` |
| `LOG_LEVEL` | Application log level | `INFO` or `DEBUG` |
| `SERVICE_NAME` | Service name in application logs and Loki labels | `adrobot` |
| `LOG_FILE` | Optional rotating JSON log file; set by Compose | `/logs/app.log` |

Compose supplies container-specific database and log paths. Restart the stack with `make docker-up` after changing settings.

## Campaigns and stream drafts

New campaign names are prefixed automatically. The first stream sends traffic from the chosen country to `REDIRECT_URL`; the fallback stream routes other traffic to the selected offer. If a stream fails after the campaign is created, the application reports the campaign ID. It does not automatically retry creation or delete the partial campaign.

In the editor, load streams by campaign ID. Adding, removing, restoring, or pinning offers changes the local draft. Publish each stream separately; cancel restores its last published snapshot. Before publishing, the application compares current upstream offer assignments with the loaded snapshot. If another user has changed them, cancel the draft and reload before making a new change. A stream with no active offers cannot be published.

The comparison reduces accidental overwrites but is not an atomic lock: another client could change a stream between the check and the update. Avoid concurrent edits to the same stream. A failed or timed-out write may have an unknown result; inspect the stream in Keitaro before retrying.

## API permissions

The application does not probe write permissions by creating resources. Keitaro may permit reading offers while denying their creation. Set `OFFER_CREATION_ENABLED=false` when that restriction is known; the UI hides creation and the server blocks direct requests. A `403` returned during other resource creation is remembered for the lifetime of the application process. These checks do not guarantee that actions without a known restriction will succeed, and process-local denials are not shared across multiple workers.

If the tracker returns `403`, ask its administrator to review the user and API-key permissions or select an existing resource. API errors are shown without exposing response bodies or credentials.

## Observability

The local stack uses Alloy to read only the application's rotating JSON log file, Loki for storage, and Grafana for viewing. Alloy does not access the Docker socket. New records include timestamp, service, level, logger, function, source line, and message. Request logging records the method, route template, status, and duration; it does not record request bodies, headers, or query parameters. Raw Uvicorn access logs and other containers are not collected by Loki.

The Grafana dashboard provides service, level, module, and function filters. In Explore, examples include:

```logql
{service="adrobot", function="log_requests"}
{service="adrobot", level="ERROR"}
```

Records written before JSON logging do not have the newer function and level labels. Loki retains logs for seven days, with deletion performed asynchronously. File rotation keeps up to three 5 MB backups; a long collector outage can result in lost records, so this setup is not an audit log with guaranteed delivery. Grafana is bound to localhost with anonymous Viewer access and temporary Explore editing enabled; Loki has no host port or built-in authentication. Do not expose this development stack to an untrusted network. Loki runs as root inside its container to write its local volume.

Use `make logs` for the application's container output and `make logs-stack` for collector and storage diagnostics.

## Development and checks

```bash
make                 # List available commands
make check           # Ruff, formatting, mypy, and all tests with coverage
make test-unit       # Unit tests only
make test-integration # Docker-backed integration tests
```

Integration tests use Testcontainers and a simulated Keitaro HTTP API; they require Docker and access to `python:3.12-slim`. They do not call a real tracker or use your key. CI runs formatting, linting, type checking, unit and container integration tests on Python 3.12 and 3.13, plus a Docker image build and Compose validation. A successful test suite does not replace an end-to-end check against the target Keitaro version and permissions.

## Project layout

```text
app/                 FastAPI assembly, routes, services, clients, and persistence
frontend/templates/  Jinja2 templates
frontend/static/     CSS and JavaScript
observability/       Alloy, Loki, and Grafana configuration
tests/unit/          Isolated unit and HTTP route tests
tests/integration/   Docker-backed integration tests
```
