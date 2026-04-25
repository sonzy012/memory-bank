"""Tests for memory_bank.ingest — session ingestion engine."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from memory_bank.db import init_db
from memory_bank.ingest import (
    _extract_artifacts,
    _extract_text,
    ingest_sessions,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def sessions_dir(tmp_path):
    d = tmp_path / "sessions"
    d.mkdir()
    return d


def _write_session(sessions_dir, session_id, meta_extra=None, turns=None, lock=False):
    meta = {
        "session_id": session_id,
        "cwd": "/tmp/project",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "title": "Test session",
        **(meta_extra or {}),
    }
    (sessions_dir / f"{session_id}.json").write_text(json.dumps(meta))
    if turns is None:
        turns = [
            {"version": "v1", "kind": "Prompt", "data": {
                "message_id": "m1",
                "content": [{"kind": "text", "data": "fix the bug in /src/main.py"}],
            }},
            {"version": "v1", "kind": "AssistantMessage", "data": {
                "message_id": "m2",
                "content": [{"kind": "text", "data": "I'll run git status to check"}],
            }},
        ]
    lines = [json.dumps(t) for t in turns]
    (sessions_dir / f"{session_id}.jsonl").write_text("\n".join(lines) + "\n")
    if lock:
        (sessions_dir / f"{session_id}.lock").write_text("{}")


def test_extract_text_list():
    content = [{"kind": "text", "data": "hello"}, {"kind": "text", "data": "world"}]
    assert _extract_text(content) == "hello\nworld"


def test_extract_text_string():
    assert _extract_text("plain text") == "plain text"


def test_extract_artifacts_file_paths():
    artifacts = _extract_artifacts("editing /src/main.py and /usr/local/bin/test")
    types = {a[0] for a in artifacts}
    assert "file" in types


def test_extract_artifacts_commands():
    artifacts = _extract_artifacts("run git status and pip install click")
    values = [a[1] for a in artifacts if a[0] == "command"]
    assert any("git status" in v for v in values)


def test_extract_artifacts_errors():
    artifacts = _extract_artifacts("Error: module not found\nTraceback: something")
    types = [a[0] for a in artifacts]
    assert "error" in types


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_basic(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, "sess-001")
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["ingested"] == 1
    assert stats["skipped"] == 0

    conn = init_db(db_path)
    sessions = conn.execute("SELECT * FROM sessions").fetchall()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "sess-001"

    messages = conn.execute("SELECT * FROM messages ORDER BY sequence").fetchall()
    assert len(messages) == 2
    assert messages[0]["kind"] == "Prompt"

    # FTS works
    fts = conn.execute(
        "SELECT * FROM messages_fts WHERE messages_fts MATCH 'bug'"
    ).fetchall()
    assert len(fts) == 1
    conn.close()


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_skips_locked(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, "sess-locked", lock=True)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["skipped"] == 1
    assert stats["ingested"] == 0


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_dedup_skips_same(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, "sess-dup")
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["skipped"] == 1


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_updates_changed(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, "sess-upd")
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    _write_session(sessions_dir, "sess-upd", meta_extra={"updated_at": "2026-02-01T00:00:00Z"})
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["updated"] == 1


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_extracts_artifacts(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, "sess-art")
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    conn = init_db(db_path)
    artifacts = conn.execute("SELECT * FROM artifacts").fetchall()
    types = {a["type"] for a in artifacts}
    assert "file" in types  # /src/main.py from the default turn
    conn.close()


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_creates_project(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {
        "returncode": 0, "stdout": "git@github.com:user/repo.git\n"
    })()
    _write_session(sessions_dir, "sess-proj")
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    conn = init_db(db_path)
    projects = conn.execute("SELECT * FROM projects").fetchall()
    assert len(projects) == 1
    assert projects[0]["git_remote"] == "git@github.com:user/repo.git"
    sessions = conn.execute("SELECT * FROM sessions").fetchall()
    assert sessions[0]["project_id"] == projects[0]["id"]
    conn.close()
