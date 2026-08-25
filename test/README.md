# FinAlly E2E Tests

Playwright end-to-end tests against the real dockerized app (built from the root `Dockerfile`),
with `LLM_MOCK=true` so chat is deterministic and no API keys are needed. The app's `/app/db`
has no volume mounted, so every run starts from a fresh seeded database.

Run everything:

```bash
docker compose -f docker-compose.test.yml up --build --force-recreate --abort-on-container-exit
```

`--force-recreate` matters: without it, `docker compose up` can reuse a stopped
`app` container from a previous run — and since `/app/db` has no volume mount, the
SQLite file written to that container's writable layer would carry over stale
data (trades, watchlist changes) into the next test run instead of starting fresh.

Test files run in order (`01-` through `06-`) since later specs (trading, portfolio
visualization, chat) build on state left by earlier ones.

To iterate locally against a manually-run container instead of Docker Compose:

```bash
npm install
BASE_URL=http://localhost:8000 npx playwright test
```
