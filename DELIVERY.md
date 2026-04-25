# Delivery: Better resume_project — generate useful pickup summary

Closes #7

## Plan

Add a `generate_resume_summary()` function that produces a human-readable markdown summary from the last 3 sessions, then wire it into the CLI (`membank resume`) and the MCP `resume_project()` tool.

## Changes

| File | Action |
|------|--------|
| `src/memory_bank/summarize.py` | **Created** — `generate_resume_summary(project_path, db_path)` |
| `src/memory_bank/cli.py` | **Modified** — added `membank resume <path>` command |
| `src/memory_bank/mcp_server.py` | **Modified** — `resume_project()` now includes `summary` field |
| `tests/test_summarize.py` | **Created** — 8 tests covering all summary sections and edge cases |
| `DELIVERY.md` | **Created** — this file |

## Summary format

```markdown
# Resume: /path/to/project

**Last worked:** 2026-01-12
**What you were doing:** Deploy v2

**Files touched:**
- deploy.sh
- config.yml

**Key decisions:**
- Use blue-green deployment

**Errors encountered:**
- Timeout on health check

**Recent sessions:**
- 2026-01-12 — Deploy v2
- 2026-01-11 — Add tests
- 2026-01-10 — Fix auth bug
```

## Testing

```bash
pytest -v tests/test_summarize.py   # 8 tests
pytest -v                           # all 46 tests pass
```

## Checklist

- [x] Read CONTRIBUTING.md
- [x] `pytest` passes (46/46)
- [x] Conventional commits used
- [x] No secrets committed
- [x] DELIVERY.md created
