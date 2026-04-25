"""Tests for memory_bank.mcp_server — MCP tools for Kiro integration."""

import os

import pytest

from memory_bank.db import init_db
from memory_bank.mcp_server import (
    get_project_context,
    resume_project,
    search_sessions,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MEMBANK_DB_PATH", str(db_path))
    conn = init_db(db_path)
    # Seed data
    conn.execute(
        "INSERT INTO projects (id, name, path, git_remote) "
        "VALUES (1, 'myapp', '/tmp/myapp', 'git@github.com:user/myapp.git')"
    )
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
        "VALUES ('s1', '/tmp/myapp', 'Fix auth bug', '2026-01-10T10:00:00Z', '2026-01-10T11:00:00Z', 1)"
    )
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
        "VALUES ('s2', '/tmp/myapp', 'Add tests', '2026-01-11T10:00:00Z', '2026-01-11T11:00:00Z', 1)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('s1', 'Prompt', 'fix the authentication bug in login module', 0)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('s1', 'AssistantMessage', 'I will update the auth handler', 1)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('s2', 'Prompt', 'add unit tests for the user service', 0)"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('s1', 'file', '/src/auth.py')"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('s1', 'command', 'pytest tests/')"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('s1', 'error', 'Error: invalid token')"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('s2', 'file', '/src/test_user.py')"
    )
    conn.commit()
    conn.close()
    return db_path


def test_search_sessions_returns_results(db):
    results = search_sessions("authentication", limit=5)
    assert len(results) == 1
    assert results[0]["title"] == "Fix auth bug"
    assert results[0]["cwd"] == "/tmp/myapp"
    assert "authentication" in results[0]["snippet"]


def test_search_sessions_no_results(db):
    results = search_sessions("nonexistent_term_xyz")
    assert results == []


def test_search_sessions_respects_limit(db):
    results = search_sessions("the", limit=1)
    assert len(results) <= 1


def test_get_project_context(db):
    ctx = get_project_context("/tmp/myapp")
    assert ctx["project_path"] == "/tmp/myapp"
    assert len(ctx["sessions"]) == 2
    assert "/src/auth.py" in ctx["files"]
    assert "pytest tests/" in ctx["commands"]


def test_get_project_context_unknown_project(db):
    ctx = get_project_context("/tmp/nonexistent")
    assert ctx["sessions"] == []
    assert ctx["files"] == []


def test_resume_project(db):
    ctx = resume_project("/tmp/myapp")
    assert ctx["last_session"]["title"] == "Add tests"
    assert ctx["last_session"]["id"] == "s2"
    assert "/src/test_user.py" in ctx["files_touched"]


def test_resume_project_unknown(db):
    ctx = resume_project("/tmp/nonexistent")
    assert "No sessions found" in ctx["message"]


def test_resume_project_includes_messages(db):
    ctx = resume_project("/tmp/myapp")
    assert len(ctx["recent_messages"]) >= 1
    assert ctx["recent_messages"][0]["kind"] == "Prompt"
