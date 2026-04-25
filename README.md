# Memory Bank

> Index your Kiro CLI sessions. Search past context. Pick up where you left off.

Memory Bank ingests Kiro CLI session files (`~/.kiro/sessions/cli/`), extracts structured context (decisions, files touched, commands, errors), stores it in SQLite with FTS5 full-text search, and serves it via a CLI and MCP server so Kiro can retrieve relevant past context automatically.

## Architecture

```
~/.kiro/sessions/cli/*.jsonl   →   Ingestion Daemon   →   SQLite + FTS5
                                        (cron/systemd)          ↓
                                                          CLI / MCP Server
                                                          ↓
                                                    Kiro retrieves context
```

## Stack

- **Python 3.12** — core language
- **SQLite + FTS5** — storage and full-text search
- **Docker** — containerized deployment
- **Click** — CLI framework
- **FastMCP** — MCP server for Kiro integration

## Quick Start

```bash
docker compose up -d
docker exec memory-bank membank ingest
docker exec memory-bank membank search "auth module"
```

## Development

```bash
git clone <repo>
cd memory-bank
pip install -e ".[dev]"
pytest
```

## License

MIT
