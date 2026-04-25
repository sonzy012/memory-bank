"""Flask web dashboard for Memory Bank."""

import os
from pathlib import Path

from flask import Flask, render_template, request

from memory_bank.db import get_connection, init_db, DEFAULT_DB_PATH


def _db_path() -> Path:
    env = os.environ.get("MEMBANK_DB_PATH")
    return Path(env) if env else DEFAULT_DB_PATH


def create_app(db_path: Path | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or _db_path()

    def get_db():
        return get_connection(app.config["DB_PATH"])

    @app.route("/")
    def dashboard():
        conn = get_db()
        try:
            stats = {
                "sessions": conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"],
                "messages": conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"],
                "artifacts": conn.execute("SELECT COUNT(*) c FROM artifacts").fetchone()["c"],
            }
            projects = conn.execute("SELECT id, name, path FROM projects ORDER BY name").fetchall()
            last = conn.execute(
                "SELECT updated_at FROM sessions ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            stats["last_ingestion"] = last["updated_at"] if last else "Never"
            return render_template("dashboard.html", stats=stats, projects=projects)
        finally:
            conn.close()

    @app.route("/projects/<int:project_id>")
    def project_detail(project_id):
        conn = get_db()
        try:
            proj = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not proj:
                return "Project not found", 404
            sessions = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions "
                "WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            from memory_bank.summarize import generate_resume_summary
            summary = generate_resume_summary(proj["path"], db_path=app.config["DB_PATH"])
            return render_template("project.html", project=proj, sessions=sessions, summary=summary)
        finally:
            conn.close()

    @app.route("/sessions/<session_id>")
    def session_detail(session_id):
        conn = get_db()
        try:
            sess = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not sess:
                return "Session not found", 404
            messages = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY sequence",
                (session_id,),
            ).fetchall()
            artifacts = conn.execute(
                "SELECT * FROM artifacts WHERE session_id = ?", (session_id,)
            ).fetchall()
            return render_template("session.html", session=sess, messages=messages, artifacts=artifacts)
        finally:
            conn.close()

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        results = []
        if query:
            conn = get_db()
            try:
                results = conn.execute(
                    "SELECT m.content, m.kind, s.id AS session_id, s.title, s.created_at "
                    "FROM messages_fts f "
                    "JOIN messages m ON m.id = f.rowid "
                    "JOIN sessions s ON s.id = m.session_id "
                    "WHERE messages_fts MATCH ? "
                    "ORDER BY rank LIMIT 50",
                    (query,),
                ).fetchall()
            finally:
                conn.close()
        return render_template("search.html", query=query, results=results)

    return app
