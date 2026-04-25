# DELIVERY — MCP Server for Kiro Integration

**Issue:** closes #5
**Branch:** agent/coder-01/task-operator-20260425-111057

## Plan

Add an MCP server to Memory Bank so Kiro CLI can query past sessions via the Model Context Protocol. Expose three tools: `search_sessions`, `get_project_context`, and `resume_project`. Add a `membank serve` CLI command to start the server.

## Changes

| File | Action | Description |
|------|--------|-------------|
| `src/memory_bank/mcp_server.py` | Created | MCP server with three tools using FastMCP |
| `src/memory_bank/cli.py` | Modified | Added `serve` command to start MCP server |
| `pyproject.toml` | Modified | Added `mcp>=1.27.0,<2` dependency |
| `tests/test_mcp.py` | Created | 8 tests covering all three MCP tools |
| `DELIVERY.md` | Created | This file |

## Testing

```bash
pytest tests/ -v          # 28 tests pass (20 existing + 8 new)
membank serve             # starts MCP server on stdio
```

## Checklist

- [x] Read CONTRIBUTING.md
- [x] `pytest` passes (28/28)
- [x] Conventional commit format
- [x] No secrets in committed files
- [x] DELIVERY.md created
