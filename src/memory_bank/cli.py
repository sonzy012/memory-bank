"""CLI interface for Memory Bank."""

import os
from pathlib import Path

import click

from memory_bank.ingest import SESSIONS_DIR, ingest_sessions


def _db_path():
    from memory_bank.db import DEFAULT_DB_PATH
    env = os.environ.get("MEMBANK_DB_PATH")
    return Path(env) if env else DEFAULT_DB_PATH


@click.group()
def cli():
    """Memory Bank — index and search your Kiro CLI sessions."""


@cli.command()
@click.option(
    "--sessions-dir", type=click.Path(exists=True), default=None,
    help="Override sessions directory.",
)
def ingest(sessions_dir):
    """Ingest Kiro CLI session files into the database."""
    path = Path(sessions_dir) if sessions_dir else Path(
        os.environ.get("MEMBANK_SESSIONS_DIR", str(SESSIONS_DIR))
    )
    stats = ingest_sessions(sessions_dir=path, db_path=_db_path())
    click.echo(
        f"Done: {stats['ingested']} ingested, {stats['updated']} updated, "
        f"{stats['skipped']} skipped."
    )


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, help="Max results.")
def search(query, limit):
    """Full-text search across all sessions."""
    from memory_bank.db import get_connection

    conn = get_connection(_db_path())
    rows = conn.execute(
        "SELECT m.content, s.title, s.cwd, s.created_at, m.kind "
        "FROM messages_fts f "
        "JOIN messages m ON m.id = f.rowid "
        "JOIN sessions s ON s.id = m.session_id "
        "WHERE messages_fts MATCH ? "
        "ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    conn.close()

    if not rows:
        click.echo("No results.")
        return
    for r in rows:
        click.echo(f"\n--- [{r['kind']}] {r['title'] or 'untitled'} ({r['created_at'][:10]})")
        click.echo(f"    cwd: {r['cwd']}")
        snippet = r["content"][:200].replace("\n", " ")
        click.echo(f"    {snippet}...")


@cli.command()
def serve():
    """Start the MCP server for Kiro integration."""
    from memory_bank.mcp_server import mcp
    mcp.run()


@cli.command()
def stats():
    """Show database statistics."""
    from memory_bank.db import get_connection, DEFAULT_DB_PATH

    db = _db_path() or DEFAULT_DB_PATH
    if not db.exists():
        click.echo(f"No database found at {db}. Run 'membank ingest' first.")
        return
    conn = get_connection(db)
    s = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
    m = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    a = conn.execute("SELECT COUNT(*) c FROM artifacts").fetchone()["c"]
    p = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
    click.echo(f"Database: {db}")
    click.echo(f"  Sessions:  {s}")
    click.echo(f"  Messages:  {m}")
    click.echo(f"  Artifacts: {a}")
    click.echo(f"  Projects:  {p}")
    click.echo()
    for row in conn.execute("SELECT name, path, git_remote FROM projects"):
        click.echo(f"  📁 {row['name']}: {row['path']}")
        if row["git_remote"]:
            click.echo(f"     remote: {row['git_remote']}")
    conn.close()


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def resume(path):
    """Show a pickup summary for a project directory."""
    from memory_bank.summarize import generate_resume_summary

    summary = generate_resume_summary(path, db_path=_db_path())
    click.echo(summary)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def project(path):
    """Show sessions and context for a project directory."""
    from memory_bank.db import get_connection

    conn = get_connection(_db_path())
    rows = conn.execute(
        "SELECT s.id, s.title, s.created_at, s.updated_at "
        "FROM sessions s "
        "JOIN projects p ON s.project_id = p.id "
        "WHERE p.path = ? "
        "ORDER BY s.created_at DESC LIMIT 20",
        (str(Path(path).resolve()),),
    ).fetchall()
    conn.close()

    if not rows:
        click.echo(f"No sessions found for {path}")
        return
    click.echo(f"Sessions for {path} ({len(rows)} found):\n")
    for r in rows:
        click.echo(f"  {r['created_at'][:16]}  {r['title'] or r['id'][:8]}")
