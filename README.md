# Pathforge FastAPI

FastAPI migration of Pathforge.

## Architecture

This repository uses a compatibility-first migration:

- FastAPI is the primary ASGI application.
- Existing Flask pages and routes are mounted through Starlette's WSGI middleware.
- Native FastAPI endpoints are available under `/api/v1`.
- Interactive API documentation is available at `/docs` and `/redoc`.

This preserves the current Pathforge interface and Supabase behavior while routes are migrated incrementally.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Copy `.env.example` to `.env` and configure the required environment variables.

## Render

The included `render.yaml` uses:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Health endpoints

- `GET /api/v1/health`
- `GET /api/v1/ready`
