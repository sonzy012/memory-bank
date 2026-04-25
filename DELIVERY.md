# DELIVERY — Web Dashboard (closes #9)

## Plan

Build a Flask web dashboard for Memory Bank with four pages: dashboard, project detail, session detail, and search. Serve on port 8080 with a dark-themed UI using plain HTML+CSS.

## Changes

| File | Action |
|------|--------|
| `src/memory_bank/web.py` | Created — Flask app factory with 4 routes |
| `src/memory_bank/templates/base.html` | Created — dark theme layout with nav |
| `src/memory_bank/templates/dashboard.html` | Created — stats cards + project list |
| `src/memory_bank/templates/project.html` | Created — sessions list + resume summary |
| `src/memory_bank/templates/session.html` | Created — messages timeline + artifacts sidebar |
| `src/memory_bank/templates/search.html` | Created — search box + FTS5 results |
| `src/memory_bank/cli.py` | Modified — added `membank web` command |
| `pyproject.toml` | Modified — added `flask>=3.1,<4` dependency |
| `tests/test_web.py` | Created — 8 tests covering all routes |

## Testing

```bash
pytest -v                    # 54 tests pass (8 new web tests)
membank web                  # starts on 0.0.0.0:8080
```

## Checklist

- [x] Read CONTRIBUTING.md
- [x] Conventional commits
- [x] `pytest` passes (54/54)
- [x] No secrets committed
- [x] Uses existing `db.py` and `summarize.py`
- [x] Flask added to pyproject.toml
- [x] CLI command `membank web` added
- [x] All 5 templates created
- [x] Dark theme, no external dependencies
- [x] DELIVERY.md created
