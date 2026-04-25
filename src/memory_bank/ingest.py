"""Ingestion engine for Memory Bank — reads Kiro CLI session files into SQLite."""

import ast
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from memory_bank.db import init_db

SESSIONS_DIR = Path.home() / ".kiro" / "sessions" / "cli"
STALE_LOCK_SECONDS = 3600  # 1 hour

# Patterns for artifact extraction
FILE_PATH_RE = re.compile(r"(?:/[\w.-]+){2,}")
COMMAND_RE = re.compile(
    r"\b(?:git|npm|pip|docker|make|cargo|pytest|cd|mkdir|rm|cp|mv|cat|grep|find|curl|wget)\s+[^\n]{1,200}"
)
ERROR_RE = re.compile(
    r"(?:Error|Exception|Traceback|FAILED|error\[)[\s:][^\n]{1,300}", re.IGNORECASE
)


def _is_valid_uuid(s: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _parse_data_field(data):
    """Parse the data field, handling both JSON and Python repr strings."""
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            try:
                parsed = ast.literal_eval(data)
            except (ValueError, SyntaxError):
                return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


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


def _is_real_file_path(path: str) -> bool:
    """Filter out URL fragments and junk paths."""
    # Must start with / and have at least one real directory component
    if not path.startswith("/"):
        return False
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return False
    # Filter URL-like path fragments
    url_indicators = {"api", "v1", "v2", "v3", "http", "https", "www"}
    if parts[0].lower() in url_indicators:
        return False
    return True


def _extract_artifacts(text: str, kind: str = "") -> list[tuple[str, str]]:
    """Extract (type, value) artifact tuples from text."""
    artifacts = []
    for m in FILE_PATH_RE.finditer(text):
        path = m.group()
        if _is_real_file_path(path):
            artifacts.append(("file", path))
    if kind == "ToolResults":
        for m in COMMAND_RE.finditer(text):
            artifacts.append(("command", m.group().strip()))
    for m in ERROR_RE.finditer(text):
        artifacts.append(("error", m.group().strip()))
    if kind == "Prompt":
        # Extract first sentence as a decision
        stripped = text.strip()
        if stripped:
            # First sentence: up to first period, newline, or end
            match = re.match(r"([^.\n]+[.]?)", stripped)
            if match:
                decision = match.group(1).strip()
                if len(decision) > 5:
                    artifacts.append(("decision", decision))
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
    sessions_dir: Path = SESSIONS_DIR, db_path=None, include_locked: bool = False,
) -> dict[str, int]:
    """Ingest all session files. Returns counts of ingested/updated/skipped."""
    from memory_bank.db import DEFAULT_DB_PATH

    conn = init_db(db_path or DEFAULT_DB_PATH)
    stats = {"ingested": 0, "updated": 0, "skipped": 0}
    project_cache: dict[str, int | None] = {}

    try:
        for meta_path in sorted(sessions_dir.glob("*.json")):
            session_id = meta_path.stem

            # Only process files whose stem is a valid UUID with a matching .jsonl
            if not _is_valid_uuid(session_id):
                stats["skipped"] += 1
                continue

            lock_path = sessions_dir / f"{session_id}.lock"
            jsonl_path = sessions_dir / f"{session_id}.jsonl"

            if not jsonl_path.exists():
                stats["skipped"] += 1
                continue

            if lock_path.exists() and not include_locked:
                lock_age = time.time() - lock_path.stat().st_mtime
                if lock_age < STALE_LOCK_SECONDS:
                    stats["skipped"] += 1
                    continue

            try:
                with open(meta_path) as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                stats["skipped"] += 1
                continue

            sid = meta.get("session_id", session_id)
            existing = conn.execute(
                "SELECT updated_at FROM sessions WHERE id = ?", (sid,)
            ).fetchone()

            if existing:
                if existing["updated_at"] == meta.get("updated_at"):
                    stats["skipped"] += 1
                    continue
                conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
                stats["updated"] += 1
            else:
                stats["ingested"] += 1

            cwd = meta.get("cwd")
            if cwd and cwd not in project_cache:
                project_cache[cwd] = _detect_project(cwd, conn)
            project_id = project_cache.get(cwd)

            conn.execute(
                "INSERT INTO sessions (id, cwd, title, created_at, updated_at, project_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, cwd, meta.get("title"),
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
                    data = _parse_data_field(turn.get("data", {}))
                    text = _extract_text(data.get("content", ""))
                    conn.execute(
                        "INSERT INTO messages (session_id, kind, content, sequence) "
                        "VALUES (?, ?, ?, ?)",
                        (sid, kind, text, seq),
                    )
                    seq += 1
                    for artifact in _extract_artifacts(text, kind):
                        all_artifacts.add(artifact)

            for atype, avalue in all_artifacts:
                conn.execute(
                    "INSERT INTO artifacts (session_id, type, value) VALUES (?, ?, ?)",
                    (sid, atype, avalue),
                )

            conn.commit()

    finally:
        conn.close()
    return stats
