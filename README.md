# Hello Web

A minimal, modern Python web app built with [FastAPI](https://fastapi.tiangolo.com/) and managed with [uv](https://docs.astral.sh/uv/).

## Run

```sh
uv run fastapi dev src/hello_web/main.py   # dev server with auto-reload on :8000
uv run hello-web                            # production-style server on $PORT (default 8000)
```

- `GET /` — Hello World page
- `GET /guestbook` — guestbook (`POST` to sign it); entries are stored in SQLite at `$GUESTBOOK_DB` (default `guestbook.db`)
- `GET /api/hello?name=Ada` — JSON greeting
- `GET /docs` — interactive API docs

## Guestbook security

- **XSS:** entries are stored as plain text and HTML-escaped on output by Jinja2 autoescaping; nothing is ever marked `safe`.
- **Content Security Policy:** pages forbid all scripts (`default-src 'none'`), so even a missed escape could not execute code.
- **SQL injection:** every query uses bound parameters.
- **Input validation:** names (≤ 50 chars) and messages (≤ 500 chars) are trimmed, Unicode-normalized, and stripped of control characters and invisible bidi overrides; limits are enforced server-side.
- **CSRF:** form posts from other sites are refused using the browser's `Sec-Fetch-Site` header.

## Test

```sh
uv run pytest
```
