# Contributing to Memory Bank

## Git Workflow

1. **Issues first** — every task is a GitHub issue. Assign yourself before starting.
2. **Branch from main** — `feat/<issue>-<short-desc>`, `fix/<issue>-<short-desc>`, `docs/<desc>`
3. **Conventional Commits** — `feat:`, `fix:`, `docs:`, `test:`, `chore:`
4. **One PR per issue** — reference the issue: `closes #N`
5. **Rebase on main** before opening PR
6. **Tests must pass** — `pytest` and `docker compose up --build`

## For AI Workers (Orchestration)

When dispatched via `spawn-agent.sh`, workers must:

1. Read this file first
2. Create a `DELIVERY.md` on their branch documenting:
   - **Plan**: what you will do
   - **Changes**: files created/modified
   - **Testing**: how to verify
   - **Checklist**: all items completed
3. Run `pytest` before committing
4. Use atomic commits with Conventional Commits format

## Pre-push Checklist

- [ ] `pytest` passes
- [ ] `docker compose build` succeeds
- [ ] No secrets in committed files
- [ ] Branch rebased on latest `main`
