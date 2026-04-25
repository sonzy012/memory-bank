"""Tests for memory_bank.web — Flask web dashboard."""

import pytest

from memory_bank.db import init_db
from memory_bank.web import create_app


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = init_db(path)
    conn.execute(
        "INSERT INTO projects (id, name, path) VALUES (1, 'testproj', '/tmp/testproj')"
    )
    conn.execute(
        "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
        "VALUES ('sess1', '/tmp/testproj', 'Fix auth bug', '2026-01-15T10:00:00', '2026-01-15T11:00:00', 1)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('sess1', 'Prompt', 'fix the authentication bug', 0)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, kind, content, sequence) "
        "VALUES ('sess1', 'AssistantMessage', 'I will fix the auth module', 1)"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('sess1', 'file', 'auth.py')"
    )
    conn.execute(
        "INSERT INTO artifacts (session_id, type, value) VALUES ('sess1', 'error', 'ImportError')"
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def client(db_path):
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_dashboard(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Dashboard" in r.data
    assert b"1" in r.data  # 1 session
    assert b"testproj" in r.data


def test_project_detail(client):
    r = client.get("/projects/1")
    assert r.status_code == 200
    assert b"testproj" in r.data
    assert b"Fix auth bug" in r.data


def test_project_not_found(client):
    r = client.get("/projects/999")
    assert r.status_code == 404


def test_session_detail(client):
    r = client.get("/sessions/sess1")
    assert r.status_code == 200
    assert b"Fix auth bug" in r.data
    assert b"fix the authentication bug" in r.data
    assert b"auth.py" in r.data


def test_session_not_found(client):
    r = client.get("/sessions/nonexistent")
    assert r.status_code == 404


def test_search_empty(client):
    r = client.get("/search")
    assert r.status_code == 200
    assert b"Search" in r.data


def test_search_with_query(client):
    r = client.get("/search?q=authentication")
    assert r.status_code == 200
    assert b"authentication" in r.data
    assert b"1 result" in r.data


def test_search_no_results(client):
    r = client.get("/search?q=nonexistentterm")
    assert r.status_code == 200
    assert b"0 result" in r.data
