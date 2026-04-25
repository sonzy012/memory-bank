"""Tests for memory_bank.ingest — session ingestion engine."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from memory_bank.db import init_db
from memory_bank.ingest import (
    STALE_LOCK_SECONDS,
    _extract_artifacts,
    _extract_text,
    _is_valid_uuid,
    _parse_data_field,
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


# Use a valid UUID for test sessions
TEST_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
TEST_UUID_2 = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
TEST_UUID_3 = "c3d4e5f6-a7b8-9012-cdef-123456789012"
TEST_UUID_4 = "d4e5f6a7-b8c9-0123-defa-234567890123"
TEST_UUID_5 = "e5f6a7b8-c9d0-1234-efab-345678901234"


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


# --- _extract_text tests ---

def test_extract_text_list():
    content = [{"kind": "text", "data": "hello"}, {"kind": "text", "data": "world"}]
    assert _extract_text(content) == "hello\nworld"


def test_extract_text_string():
    assert _extract_text("plain text") == "plain text"


# --- _parse_data_field tests ---

def test_parse_data_field_dict():
    assert _parse_data_field({"key": "val"}) == {"key": "val"}


def test_parse_data_field_json_string():
    assert _parse_data_field('{"key": "val"}') == {"key": "val"}


def test_parse_data_field_python_repr():
    """Problem 1: Python repr strings should be parsed via ast.literal_eval."""
    data_str = "{'message_id': 'abc', 'content': [{'kind': 'text', 'data': 'hello'}]}"
    result = _parse_data_field(data_str)
    assert result["message_id"] == "abc"
    assert result["content"][0]["data"] == "hello"


def test_parse_data_field_invalid():
    assert _parse_data_field("not valid at all {{{") == {}


# --- _extract_artifacts tests ---

def test_extract_artifacts_file_paths():
    artifacts = _extract_artifacts("editing /src/main.py and /usr/local/bin/test")
    types = {a[0] for a in artifacts}
    assert "file" in types


def test_extract_artifacts_filters_url_fragments():
    """File path extraction should filter URL-like paths."""
    artifacts = _extract_artifacts("GET /api/v1/users/123")
    file_artifacts = [a for a in artifacts if a[0] == "file"]
    assert len(file_artifacts) == 0


def test_extract_artifacts_commands_only_from_tool_results():
    """Problem 3: Commands should only be extracted from ToolResults."""
    text = "run git status and pip install click"
    # No commands when kind is not ToolResults
    artifacts_prompt = _extract_artifacts(text, kind="Prompt")
    cmd_prompt = [a for a in artifacts_prompt if a[0] == "command"]
    assert len(cmd_prompt) == 0

    # Commands extracted when kind is ToolResults
    artifacts_tool = _extract_artifacts(text, kind="ToolResults")
    cmd_tool = [a for a in artifacts_tool if a[0] == "command"]
    assert any("git status" in v for _, v in cmd_tool)


def test_extract_artifacts_errors():
    artifacts = _extract_artifacts("Error: module not found\nTraceback: something")
    types = [a[0] for a in artifacts]
    assert "error" in types


def test_extract_artifacts_decision_from_prompt():
    """Problem 3: Decisions extracted from Prompt messages."""
    artifacts = _extract_artifacts("Refactor the auth module to use JWT tokens.", kind="Prompt")
    decisions = [a for a in artifacts if a[0] == "decision"]
    assert len(decisions) == 1
    assert "Refactor the auth module" in decisions[0][1]


def test_extract_artifacts_no_decision_from_assistant():
    artifacts = _extract_artifacts("I will refactor the auth module.", kind="AssistantMessage")
    decisions = [a for a in artifacts if a[0] == "decision"]
    assert len(decisions) == 0


# --- _is_valid_uuid tests ---

def test_is_valid_uuid():
    assert _is_valid_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True
    assert _is_valid_uuid("not-a-uuid") is False
    assert _is_valid_uuid("session-metadata") is False


# --- ingest_sessions tests ---

@patch("memory_bank.ingest.subprocess.run")
def test_ingest_basic(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["ingested"] == 1
    assert stats["skipped"] == 0

    conn = init_db(db_path)
    sessions = conn.execute("SELECT * FROM sessions").fetchall()
    assert len(sessions) == 1
    assert sessions[0]["id"] == TEST_UUID

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
def test_ingest_skips_fresh_locked(mock_run, sessions_dir, db_path):
    """Sessions with a fresh lock (< 1 hour old) are skipped."""
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID, lock=True)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["skipped"] == 1
    assert stats["ingested"] == 0


@patch("memory_bank.ingest.subprocess.run")
@patch("memory_bank.ingest.time")
def test_ingest_ingests_stale_locked(mock_time, mock_run, sessions_dir, db_path):
    """Sessions with a stale lock (>= 1 hour old) are ingested."""
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID, lock=True)
    lock_path = sessions_dir / f"{TEST_UUID}.lock"
    lock_mtime = lock_path.stat().st_mtime
    mock_time.time.return_value = lock_mtime + STALE_LOCK_SECONDS + 1
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["ingested"] == 1
    assert stats["skipped"] == 0


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_include_locked_forces_ingestion(mock_run, sessions_dir, db_path):
    """--include-locked ingests even freshly locked sessions."""
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID, lock=True)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path, include_locked=True)
    assert stats["ingested"] == 1
    assert stats["skipped"] == 0


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_skips_non_uuid(mock_run, sessions_dir, db_path):
    """Problem 2: Non-UUID .json files should be skipped."""
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    # Write a non-UUID session file (like directory metadata)
    (sessions_dir / "not-a-uuid.json").write_text('{"session_id": "x"}')
    (sessions_dir / "not-a-uuid.jsonl").write_text("")
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["skipped"] == 1
    assert stats["ingested"] == 0


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_dedup_skips_same(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID_2)
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["skipped"] == 1


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_updates_changed(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID_3)
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    _write_session(sessions_dir, TEST_UUID_3, meta_extra={"updated_at": "2026-02-01T00:00:00Z"})
    stats = ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)
    assert stats["updated"] == 1


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_extracts_artifacts(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    _write_session(sessions_dir, TEST_UUID_4)
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    conn = init_db(db_path)
    artifacts = conn.execute("SELECT * FROM artifacts").fetchall()
    types = {a["type"] for a in artifacts}
    assert "file" in types  # /src/main.py from the default turn
    assert "decision" in types  # first sentence of the Prompt
    conn.close()


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_creates_project(mock_run, sessions_dir, db_path):
    mock_run.return_value = type("R", (), {
        "returncode": 0, "stdout": "git@github.com:user/repo.git\n"
    })()
    _write_session(sessions_dir, TEST_UUID_5)
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    conn = init_db(db_path)
    projects = conn.execute("SELECT * FROM projects").fetchall()
    assert len(projects) == 1
    assert projects[0]["git_remote"] == "git@github.com:user/repo.git"
    sessions = conn.execute("SELECT * FROM sessions").fetchall()
    assert sessions[0]["project_id"] == projects[0]["id"]
    conn.close()


@patch("memory_bank.ingest.subprocess.run")
def test_ingest_python_repr_data(mock_run, sessions_dir, db_path):
    """Problem 1: Sessions with Python repr data strings should be parsed."""
    mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
    turns = [
        {
            "version": "v1",
            "kind": "Prompt",
            "data": "{'message_id': 'abc', 'content': [{'kind': 'text', 'data': 'hello world'}]}",
        },
    ]
    _write_session(sessions_dir, TEST_UUID, turns=turns)
    ingest_sessions(sessions_dir=sessions_dir, db_path=db_path)

    conn = init_db(db_path)
    messages = conn.execute("SELECT * FROM messages").fetchall()
    assert len(messages) == 1
    assert messages[0]["content"] == "hello world"
    conn.close()
