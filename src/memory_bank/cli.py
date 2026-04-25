"""CLI interface for Memory Bank."""

import click

from memory_bank.ingest import SESSIONS_DIR, ingest_sessions


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
    from pathlib import Path

    path = Path(sessions_dir) if sessions_dir else SESSIONS_DIR
    stats = ingest_sessions(sessions_dir=path)
    click.echo(
        f"Done: {stats['ingested']} ingested, {stats['updated']} updated, "
        f"{stats['skipped']} skipped."
    )
