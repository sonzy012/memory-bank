# Delivery — DB Schema & Ingestion Engine

Closes #1 (DB schema), closes #2 (ingestion engine).

## Plan

1. Create SQLite + FTS5 schema with tables: projects, sessions, messages, artifacts, messages_fts
2. Build ingestion engine to read `~/.kiro/sessions/cli/` files
3. Set up package with pyproject.toml and CLI entry point

## Changes

| File | Description |
|------|-------------|
| `pyproject.toml` | Package config with click dependency |
| `src/memory_bank/__init__.py` | Package init |
| `src/memory_bank/db.py` | Schema (4 tables + FTS5 + triggers), `init_db()`, `get_connection()` |
| `src/memory_bank/ingest.py` | Session ingestion: reads .json/.jsonl, extracts artifacts, deduplicates, detects projects |
| `src/memory_bank/cli.py` | `membank ingest` CLI command |
| `tests/test_db.py` | 9 tests — schema creation, FTS5, constraints, triggers |
| `tests/test_ingest.py` | 11 tests — extraction, ingestion, dedup, locking, project detection |
| `tests/test_cli.py` | 1 test — CLI command output |

## Testing

```bash
PYTHONPATH=src python3 -m pytest tests/ -v
# 20 passed
```

## Checklist

- [x] Read CONTRIBUTING.md
- [x] DB schema with FTS5 virtual table and triggers
- [x] Ingestion reads .json metadata and .jsonl conversation turns
- [x] Artifact extraction (files, commands, errors)
- [x] Deduplication by session_id (skip same, update if changed)
- [x] Skip sessions with .lock files
- [x] Auto-detect project from cwd + git remote
- [x] CLI `membank ingest` command
- [x] pytest passes (20/20)
- [x] Conventional commits
