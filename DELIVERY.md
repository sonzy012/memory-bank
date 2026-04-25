# Delivery: Fix stale lock handling

**Issue:** closes #10

## Plan

Replace the blanket lock-file skip in `ingest_sessions` with age-based logic:
- Fresh locks (< 1 hour): skip (session truly active)
- Stale locks (≥ 1 hour): ingest anyway (Kiro never cleaned up)
- `--include-locked` CLI flag: bypass all lock checks

## Changes

| File | Change |
|------|--------|
| `src/memory_bank/ingest.py` | Added `time` import, `STALE_LOCK_SECONDS` constant, age-based lock check, `include_locked` parameter |
| `src/memory_bank/cli.py` | Added `--include-locked` flag to `ingest` command |
| `tests/test_ingest.py` | Replaced `test_ingest_skips_locked` with 3 tests: fresh lock skip, stale lock ingest, include_locked override |
| `tests/test_cli.py` | Added `test_ingest_include_locked_flag` |

## Testing

```bash
pytest -v   # 57 passed
```

## Checklist

- [x] `pytest` passes (57/57)
- [x] Conventional commit format
- [x] DELIVERY.md created
- [x] No secrets committed
