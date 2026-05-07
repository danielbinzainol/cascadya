# c-market Backoffice

## Local run

```bash
uv sync --locked --dev
uv run uvicorn src.backoffice.api.main:app --host 127.0.0.1 --port 8000
```

- App: `http://127.0.0.1:8000/backoffice`
- Health: `http://127.0.0.1:8000/health`
- Docs: `http://127.0.0.1:8000/docs` (if enabled)

## Docker run (production-style)

```bash
docker run -d \
  --name c-market-backoffice \
  -p 80:8000 \
  -v /srv/c-market/data:/app/data \
  -e C_MARKET_DATA_ROOT=/app/data \
  -e BACKOFFICE_DISABLE_DOCS=true \
  -e BACKOFFICE_REQUIRE_API_KEY=true \
  -e BACKOFFICE_API_KEY=<strong-secret> \
  --restart unless-stopped \
  c-market-backoffice:latest
```

## Docker Compose

```bash
docker compose up --build -d
docker compose logs -f backoffice
docker compose down
```

## Required data layout

Mounted data root should contain:

- `/app/data/inariz/raw/*.csv`

## Environment variables

- `C_MARKET_DATA_ROOT` (example: `/app/data`)
- `INARIZ_DATA_ROOT` (optional project override)
- `BACKOFFICE_DISABLE_DOCS` (`true`/`false`)
- `BACKOFFICE_REQUIRE_API_KEY` (`true`/`false`)
- `BACKOFFICE_API_KEY`
- `BACKOFFICE_API_KEY_HEADER` (default: `X-API-Key`)

## Quick ops

```bash
curl -f http://127.0.0.1:8000/health
docker logs -f c-market-backoffice
```
