# Flask to FastAPI migration

## Current stage

FastAPI owns the ASGI process, health checks, OpenAPI schema, and future native
API routers. The original Flask application is mounted at the root with
`WSGIMiddleware`, preserving existing pages, sessions, templates, admin tools,
and Supabase calls.

## Why this is staged

Replacing every route in one change would risk breaking authentication,
redirects, CSRF checks, template endpoint names, and database behavior. The
compatibility layer allows routes to be moved one router at a time and tested
against the existing behavior.

## Next migration units

1. Move JSON-only endpoints from `routes/api_routes.py` into FastAPI routers.
2. Replace Flask session helpers with signed Starlette sessions or Supabase
   bearer-token dependencies.
3. Move page handlers to FastAPI and Jinja2Templates.
4. Remove Flask and WSGIMiddleware after parity tests pass.

## Missing binary media

GitHub's connected file interface does not expose binary repository blobs.
Source code, templates, CSS, JavaScript, JSON, SQL, and SVG assets were copied.
PNG/ICO media should be copied from the original repository with a normal Git
clone before production deployment.
