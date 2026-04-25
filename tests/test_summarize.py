"""Tests for memory_bank.summarize — resume summary generation."""

import pytest

from memory_bank.db import init_db
from memory_bank.summarize import generate_resume_summary


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO projects (id, name, path) VALUES (1, 'myapp', '/tmp/myapp')"
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
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
        "VALUES ('s3', '/tmp/myapp', 'Deploy v2', '2026-01-12T10:00:00Z', '2026-01-12T11:00:00Z', 1)"
    )
    conn.execute("INSERT INTO artifacts (session_id, type, value) VALUES ('s3', 'file', 'deploy.sh')")
    conn.execute("INSERT INTO artifacts (session_id, type, value) VALUES ('s3', 'file', 'config.yml')")
    conn.execute("INSERT INTO artifacts (session_id, type, value) VALUES ('s3', 'decision', 'Use blue-green deployment')")
    conn.execute("INSERT INTO artifacts (session_id, type, value) VALUES ('s3', 'error', 'Timeout on health check')")
    conn.commit()
    conn.close()
    return db_path


def test_summary_contains_last_worked(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "**Last worked:** 2026-01-12" in summary


def test_summary_contains_what_doing(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "**What you were doing:** Deploy v2" in summary


def test_summary_contains_files(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "deploy.sh" in summary
    assert "config.yml" in summary


def test_summary_contains_decisions(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "Use blue-green deployment" in summary


def test_summary_contains_errors(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "Timeout on health check" in summary


def test_summary_contains_recent_sessions(db):
    summary = generate_resume_summary("/tmp/myapp", db_path=db)
    assert "Deploy v2" in summary
    assert "Add tests" in summary
    assert "Fix auth bug" in summary


def test_summary_no_sessions(db):
    summary = generate_resume_summary("/tmp/nonexistent", db_path=db)
    assert "No sessions found" in summary


def test_summary_limits_to_3_sessions(db, tmp_path):
    """Only the last 3 sessions should appear in recent sessions."""
    db_path = tmp_path / "test2.db"
    conn = init_db(db_path)
    conn.execute("INSERT INTO projects (id, name, path) VALUES (1, 'p', '/tmp/p')")
    for i in range(5):
        conn.execute(
            "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
            f"VALUES ('s{i}', '/tmp/p', 'Session {i}', '2026-01-{10+i:02d}T10:00:00Z', '2026-01-{10+i:02d}T11:00:00Z', 1)"
        )
    conn.commit()
    conn.close()
    summary = generate_resume_summary("/tmp/p", db_path=db_path)
    assert "Session 4" in summary
    assert "Session 3" in summary
    assert "Session 2" in summary
    assert "Session 1" not in summary
