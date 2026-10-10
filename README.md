# Hello Web

A minimal, modern Python web app built with [FastAPI](https://fastapi.tiangolo.com/) and managed with [uv](https://docs.astral.sh/uv/).

## Run

```sh
uv run fastapi dev src/hello_web/main.py   # dev server with auto-reload on :8000
uv run hello-web                            # production-style server on $PORT (default 8000)
```

- `GET /` — Hello World page
- `GET /guestbook` — guestbook (`POST` to sign it); entries are stored in SQLite at `$GUESTBOOK_DB` (default `guestbook.db`)
- `GET /ask` — ask the local AI model from a text box
- `POST /ollama/` — JSON API: `{"prompt": "..."}` → `{"response": "..."}`, answered by a local [Ollama](https://ollama.com/) server (`OLLAMA_URL`, default `http://localhost:11434`) using `OLLAMA_MODEL` (default `qwen3.8`)
- `GET /api/hello?name=Ada` — JSON greeting
- `GET /docs` — interactive API docs

## Security

The guestbook and the `/ollama/` API share the same protections. Prompts are limited to 1000 characters, and the AI has its own one-per-minute budget, separate from the guestbook.

- **Ollama exposure:** only `/ollama/` is public, and it can only run one prompt on the configured model. Keep Ollama itself bound to localhost (its default), so its full API (pulling and deleting models, etc.) stays private. Model answers are treated as untrusted text and never rendered as HTML.

- **XSS:** entries are stored as plain text and HTML-escaped on output by Jinja2 autoescaping; nothing is ever marked `safe`.
- **Content Security Policy:** only the app's own script files may run (`script-src 'self'`); inline and injected scripts are blocked, so even a missed escape could not execute code.
- **SQL injection:** every query uses bound parameters.
- **Input validation:** names (≤ 50 chars) and messages (≤ 500 chars) are trimmed, Unicode-normalized, and stripped of control characters and invisible bidi overrides; limits are enforced server-side.
- **CSRF:** form posts from other sites are refused using the browser's `Sec-Fetch-Site` header.
- **Rate limiting:** each client IP may post once per minute; extra attempts get `429` with `Retry-After` and a live countdown, and the draft is kept. Behind a reverse proxy, set uvicorn's `FORWARDED_ALLOW_IPS` to the proxy's address so the real client IP is used (only trusted proxies may set `X-Forwarded-For`).

## Test

```sh
uv run pytest
```
