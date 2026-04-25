"""MCP server for Memory Bank — exposes session search tools to Kiro CLI."""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from memory_bank.db import get_connection, init_db

mcp = FastMCP("memory-bank")


def _get_conn():
    env = os.environ.get("MEMBANK_DB_PATH")
    db_path = Path(env) if env else None
    from memory_bank.db import DEFAULT_DB_PATH
    return get_connection(db_path or DEFAULT_DB_PATH)


@mcp.tool()
def search_sessions(query: str, limit: int = 10) -> list[dict]:
    """Search past Kiro CLI sessions using full-text search.

    Returns matching messages with session title, working directory, date, and a snippet.
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT m.content, s.title, s.cwd, s.created_at, m.kind "
            "FROM messages_fts f "
            "JOIN messages m ON m.id = f.rowid "
            "JOIN sessions s ON s.id = m.session_id "
            "WHERE messages_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (query, limit),
        ).fetchall()
        return [
            {
                "title": r["title"] or "untitled",
                "cwd": r["cwd"],
                "date": r["created_at"],
                "kind": r["kind"],
                "snippet": r["content"][:300],
            }
            for r in rows
        ]
    finally:
        conn.close()


@mcp.tool()
def get_project_context(project_path: str) -> dict:
    """Get context for a project: recent sessions, files touched, and commands run."""
    resolved = str(Path(project_path).resolve())
    conn = _get_conn()
    try:
        sessions = conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at "
            "FROM sessions s "
            "JOIN projects p ON s.project_id = p.id "
            "WHERE p.path = ? "
            "ORDER BY s.created_at DESC LIMIT 20",
            (resolved,),
        ).fetchall()
        if not sessions:
            return {"project_path": resolved, "sessions": [], "files": [], "commands": []}

        session_ids = [s["id"] for s in sessions]
        placeholders = ",".join("?" * len(session_ids))

        files = conn.execute(
            f"SELECT DISTINCT value FROM artifacts "
            f"WHERE session_id IN ({placeholders}) AND type = 'file'",
            session_ids,
        ).fetchall()

        commands = conn.execute(
            f"SELECT DISTINCT value FROM artifacts "
            f"WHERE session_id IN ({placeholders}) AND type = 'command'",
            session_ids,
        ).fetchall()

        return {
            "project_path": resolved,
            "sessions": [
                {"id": s["id"], "title": s["title"], "created_at": s["created_at"]}
                for s in sessions
            ],
            "files": [r["value"] for r in files],
            "commands": [r["value"] for r in commands],
        }
    finally:
        conn.close()


@mcp.tool()
def resume_project(project_path: str) -> dict:
    """Get resumption context for a project: last session summary, files changed, and unfinished work."""
    from memory_bank.summarize import generate_resume_summary

    resolved = str(Path(project_path).resolve())
    conn = _get_conn()
    try:
        session = conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, s.cwd "
            "FROM sessions s "
            "JOIN projects p ON s.project_id = p.id "
            "WHERE p.path = ? "
            "ORDER BY s.created_at DESC LIMIT 1",
            (resolved,),
        ).fetchone()
        if not session:
            return {"project_path": resolved, "message": "No sessions found for this project."}

        sid = session["id"]

        messages = conn.execute(
            "SELECT kind, content FROM messages "
            "WHERE session_id = ? ORDER BY sequence",
            (sid,),
        ).fetchall()

        artifacts = conn.execute(
            "SELECT type, value FROM artifacts WHERE session_id = ?",
            (sid,),
        ).fetchall()

        last_messages = messages[-5:] if len(messages) > 5 else messages

        env = os.environ.get("MEMBANK_DB_PATH")
        db_path = Path(env) if env else None
        from memory_bank.db import DEFAULT_DB_PATH
        summary = generate_resume_summary(project_path, db_path=db_path or DEFAULT_DB_PATH)

        return {
            "project_path": resolved,
            "summary": summary,
            "last_session": {
                "id": sid,
                "title": session["title"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
            },
            "recent_messages": [
                {"kind": m["kind"], "snippet": m["content"][:300]}
                for m in last_messages
            ],
            "files_touched": [a["value"] for a in artifacts if a["type"] == "file"],
            "commands_run": [a["value"] for a in artifacts if a["type"] == "command"],
            "errors": [a["value"] for a in artifacts if a["type"] == "error"],
        }
    finally:
        conn.close()
