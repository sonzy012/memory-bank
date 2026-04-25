"""Ingestion engine for Memory Bank — reads Kiro CLI session files into SQLite."""

import json
import re
import subprocess
from pathlib import Path

from memory_bank.db import init_db

SESSIONS_DIR = Path.home() / ".kiro" / "sessions" / "cli"

# Patterns for artifact extraction
FILE_PATH_RE = re.compile(r"(?:/[\w./-]+){2,}")
COMMAND_RE = re.compile(
    r"\b(?:git|npm|pip|docker|make|cargo|pytest|cd|mkdir|rm|cp|mv|cat|grep|find|curl|wget)\s+[^\n]{1,200}"
)
ERROR_RE = re.compile(
    r"(?:Error|Exception|Traceback|FAILED|error\[)[\s:][^\n]{1,300}", re.IGNORECASE
)


def _extract_text(content) -> str:
    """Extract plain text from a message content field (list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                data = block.get("data", "")
                if block.get("kind") == "text" and isinstance(data, str):
                    parts.append(data)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _extract_artifacts(text: str) -> list[tuple[str, str]]:
    """Extract (type, value) artifact tuples from text."""
    artifacts = []
    for m in FILE_PATH_RE.finditer(text):
        artifacts.append(("file", m.group()))
    for m in COMMAND_RE.finditer(text):
        artifacts.append(("command", m.group().strip()))
    for m in ERROR_RE.finditer(text):
        artifacts.append(("error", m.group().strip()))
    return artifacts


def _detect_project(cwd: str | None, conn) -> int | None:
    """Detect or create a project from cwd. Returns project_id or None."""
    if not cwd:
        return None
    git_remote = None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            git_remote = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    name = Path(cwd).name
    row = conn.execute(
        "SELECT id FROM projects WHERE path = ?", (cwd,)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO projects (name, path, git_remote) VALUES (?, ?, ?)",
        (name, cwd, git_remote),
    )
    return cur.lastrowid


def ingest_sessions(
    sessions_dir: Path = SESSIONS_DIR, db_path=None
) -> dict[str, int]:
    """Ingest all session files. Returns counts of ingested/updated/skipped."""
    from memory_bank.db import DEFAULT_DB_PATH

    conn = init_db(db_path or DEFAULT_DB_PATH)
    stats = {"ingested": 0, "updated": 0, "skipped": 0}

    for meta_path in sorted(sessions_dir.glob("*.json")):
        session_id = meta_path.stem
        lock_path = sessions_dir / f"{session_id}.lock"
        jsonl_path = sessions_dir / f"{session_id}.jsonl"

        if lock_path.exists():
            stats["skipped"] += 1
            continue
        if not jsonl_path.exists():
            stats["skipped"] += 1
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        sid = meta.get("session_id", session_id)
        existing = conn.execute(
            "SELECT updated_at FROM sessions WHERE id = ?", (sid,)
        ).fetchone()

        if existing:
            if existing["updated_at"] == meta.get("updated_at"):
                stats["skipped"] += 1
                continue
            # Session updated — delete old data and re-ingest
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM artifacts WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            stats["updated"] += 1
        else:
            stats["ingested"] += 1

        project_id = _detect_project(meta.get("cwd"), conn)
        conn.execute(
            "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, meta.get("cwd"), meta.get("title"),
             meta.get("created_at"), meta.get("updated_at"), project_id),
        )

        all_artifacts: set[tuple[str, str]] = set()
        seq = 0
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    turn = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = turn.get("kind")
                if kind not in ("Prompt", "AssistantMessage", "ToolResults"):
                    continue
                text = _extract_text(turn.get("data", {}).get("content", ""))
                conn.execute(
                    "INSERT INTO messages (session_id, kind, content, sequence) "
                    "VALUES (?, ?, ?, ?)",
                    (sid, kind, text, seq),
                )
                seq += 1
                for artifact in _extract_artifacts(text):
                    all_artifacts.add(artifact)

        for atype, avalue in all_artifacts:
            conn.execute(
                "INSERT INTO artifacts (session_id, type, value) VALUES (?, ?, ?)",
                (sid, atype, avalue),
            )

        conn.commit()

    conn.close()
    return stats
