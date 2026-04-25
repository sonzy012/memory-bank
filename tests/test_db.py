"""Tests for memory_bank.db — schema and connection management."""

import sqlite3
from pathlib import Path

import pytest

from memory_bank.db import get_connection, init_db


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_init_db_creates_tables(db_path):
    conn = init_db(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')"
        ).fetchall()
    }
    assert "sessions" in tables
    assert "messages" in tables
    assert "artifacts" in tables
    assert "projects" in tables
    assert "messages_fts" in tables
    assert "messages_ai" in tables
    conn.close()


def test_init_db_idempotent(db_path):
    conn1 = init_db(db_path)
    conn1.close()
    conn2 = init_db(db_path)
    conn2.close()


def test_get_connection_row_factory(db_path):
    init_db(db_path)
    conn = get_connection(db_path)
    assert conn.row_factory == sqlite3.Row
    conn.close()


def test_foreign_keys_enabled(db_path):
    conn = init_db(db_path)
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def test_fts5_search(db_path):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at) "
        "VALUES ('s1', '/tmp', 'test', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('s1', 'Prompt', 'fix the authentication bug in login module', 0)"
    )
    conn.commit()
    results = conn.execute(
        "SELECT * FROM messages_fts WHERE messages_fts MATCH 'authentication'"
    ).fetchall()
    assert len(results) == 1
    conn.close()


def test_message_kind_constraint(db_path):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at) "
        "VALUES ('s1', '/tmp', 'test', '2026-01-01', '2026-01-01')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO messages (session_id, kind, content, sequence) "
            "VALUES ('s1', 'InvalidKind', 'test', 0)"
        )
    conn.close()


def test_artifact_type_constraint(db_path):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at) "
        "VALUES ('s1', '/tmp', 'test', '2026-01-01', '2026-01-01')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO artifacts (session_id, type, value) "
            "VALUES ('s1', 'invalid', 'test')"
        )
    conn.close()


def test_fts_delete_trigger(db_path):
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at) "
        "VALUES ('s1', '/tmp', 'test', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('s1', 'Prompt', 'unique_search_term_xyz', 0)"
    )
    conn.commit()
    conn.execute("DELETE FROM messages WHERE session_id = 's1'")
    conn.commit()
    results = conn.execute(
        "SELECT * FROM messages_fts WHERE messages_fts MATCH 'unique_search_term_xyz'"
    ).fetchall()
    assert len(results) == 0
    conn.close()
