"""Generate human-readable resume summaries for projects."""

from pathlib import Path

from memory_bank.db import get_connection, DEFAULT_DB_PATH


def generate_resume_summary(project_path: str, db_path: Path = DEFAULT_DB_PATH) -> str:
    """Build a markdown summary for resuming work on a project."""
    resolved = str(Path(project_path).resolve())
    conn = get_connection(db_path)
    try:
        sessions = conn.execute(
            "SELECT s.id, s.title, s.created_at "
            "FROM sessions s "
            "JOIN projects p ON s.project_id = p.id "
            "WHERE p.path = ? "
            "ORDER BY s.created_at DESC LIMIT 3",
            (resolved,),
        ).fetchall()

        if not sessions:
            return f"No sessions found for {resolved}."

        last = sessions[0]
        sid = last["id"]

        artifacts = conn.execute(
            "SELECT type, value FROM artifacts WHERE session_id = ?",
            (sid,),
        ).fetchall()

        files = [a["value"] for a in artifacts if a["type"] == "file"]
        decisions = [a["value"] for a in artifacts if a["type"] == "decision"]
        errors = [a["value"] for a in artifacts if a["type"] == "error"]

        lines = [
            f"# Resume: {resolved}\n",
            f"**Last worked:** {last['created_at'][:10]}",
            f"**What you were doing:** {last['title'] or 'untitled'}",
        ]

        if files:
            lines.append("\n**Files touched:**")
            lines.extend(f"- {f}" for f in files)

        if decisions:
            lines.append("\n**Key decisions:**")
            lines.extend(f"- {d}" for d in decisions)

        if errors:
            lines.append("\n**Errors encountered:**")
            lines.extend(f"- {e}" for e in errors)

        lines.append("\n**Recent sessions:**")
        for s in sessions:
            lines.append(f"- {s['created_at'][:10]} — {s['title'] or 'untitled'}")

        return "\n".join(lines)
    finally:
        conn.close()
