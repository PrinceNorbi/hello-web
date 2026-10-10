# Hello Web

A minimal, modern Python web app built with [FastAPI](https://fastapi.tiangolo.com/) and managed with [uv](https://docs.astral.sh/uv/).

## Run

```sh
uv run fastapi dev src/hello_web/main.py   # dev server with auto-reload on :8000
uv run hello-web                            # production-style server on $PORT (default 8000)
```

- `GET /` — Hello World page
- `GET /api/hello?name=Ada` — JSON greeting
- `GET /docs` — interactive API docs

## Test

```sh
uv run pytest
```
