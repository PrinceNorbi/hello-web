import json
import logging
import logging.handlers
import os
from pathlib import Path
from time import perf_counter
from typing import Annotated
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from hello_web import guestbook, ollama

logger = logging.getLogger(__name__)

# One JSON line per POST request, written to stderr or to PAYLOAD_LOG_FILE when set.
# WatchedFileHandler reopens the file after logrotate moves it.
PAYLOAD_LOG_MAX = 2000  # bytes of each request body to keep
payload_log = logging.getLogger("hello_web.payloads")
payload_log.setLevel(logging.INFO)
_payload_handler = (
    logging.handlers.WatchedFileHandler(os.environ["PAYLOAD_LOG_FILE"])
    if os.environ.get("PAYLOAD_LOG_FILE")
    else logging.StreamHandler()
)
_payload_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
payload_log.addHandler(_payload_handler)

BASE_DIR = Path(__file__).parent

#app = Flask(__name__)
app = FastAPI(title="Hello Web")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# Jinja2Templates autoescapes .html templates, so user text is always rendered inert.
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Only our own static files may run as scripts; inline and injected scripts are blocked as a second
# line of defense against XSS.
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    # Swagger UI and ReDoc load scripts from a CDN, so they keep FastAPI's defaults.
    if not request.url.path.startswith(("/docs", "/redoc")):
        response.headers["Content-Security-Policy"] = CSP
    return response


def reject_cross_site(request: Request) -> None:
    # Browsers label every request's origin; refuse submissions made from other sites (CSRF).
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        raise HTTPException(status_code=403, detail="Cross-site submissions are not allowed.")


def client_ip(request: Request) -> str:
    # Behind a reverse proxy, uvicorn derives the client address from X-Forwarded-For only when the
    # proxy's IP is listed in FORWARDED_ALLOW_IPS, so clients cannot spoof it.
    return request.client.host if request.client else ""


def parse_payload(body: bytes, content_type: str):
    text = body[:PAYLOAD_LOG_MAX].decode("utf-8", errors="replace")
    if content_type.startswith("application/x-www-form-urlencoded"):
        return dict(parse_qsl(text, keep_blank_values=True))
    if content_type.startswith("application/json"):
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


@app.middleware("http")
async def log_post_payloads(request: Request, call_next):
    if request.method != "POST":
        return await call_next(request)
    started = perf_counter()
    body = await request.body()  # Starlette replays the cached body to the route
    response = await call_next(request)
    entry = {
        "client": client_ip(request),
        "path": request.url.path,
        "status": response.status_code,
        # Server-side time to handle the request; for /ollama/ this is mostly the model's answer time.
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "payload": parse_payload(body, request.headers.get("content-type", "")),
    }
    # json.dumps escapes newlines, control and non-ASCII characters, so user input cannot forge
    # extra log lines or hide text from someone reading the log.
    payload_log.info(json.dumps(entry))
    return response


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Browsers request /favicon.ico on their own, even for pages without a <link rel="icon">.
    return FileResponse(BASE_DIR / "static" / "favicon.ico", media_type="image/x-icon")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    context = {"model": ollama.model(), "prompt_max": ollama.PROMPT_MAX}
    return templates.TemplateResponse(request, "ask.html", context)


class Prompt(BaseModel):
    prompt: str


@app.post("/ollama/")
async def ask_ollama(request: Request, body: Prompt) -> dict[str, str]:
    """Send one prompt to the local Ollama model; only this narrow call is exposed, not Ollama's API."""
    reject_cross_site(request)
    prompt = guestbook.clean_text(body.prompt, multiline=True)
    if not prompt:
        raise HTTPException(status_code=422, detail="Please write a prompt.")
    if len(prompt) > ollama.PROMPT_MAX:
        raise HTTPException(
            status_code=422, detail=f"Prompt must be at most {ollama.PROMPT_MAX} characters."
        )
    # Its own key gives the AI a separate one-per-minute budget from the guestbook.
    retry_after = await run_in_threadpool(guestbook.claim_slot, f"ollama:{client_ip(request)}")
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="You've reached the limit of one post per minute.",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        return {"response": await ollama.generate(prompt)}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The AI model took too long to answer.")
    except httpx.HTTPError as exc:
        # Keep Ollama's details in the server log; clients only learn that it is unavailable.
        logger.warning("Ollama request failed: %r", exc)
        raise HTTPException(status_code=502, detail="The AI model is not available right now.")


def render_guestbook(
    request: Request, *, errors=(), retry_after=0, name="", message="", status_code=200
):
    context = {
        "entries": guestbook.list_entries(),
        "errors": errors,
        "retry_after": retry_after,
        "name": name,
        "message": message,
        "name_max": guestbook.NAME_MAX,
        "message_max": guestbook.MESSAGE_MAX,
    }
    return templates.TemplateResponse(request, "guestbook.html", context, status_code=status_code)


@app.get("/guestbook", response_class=HTMLResponse)
def guestbook_page(request: Request):
    return render_guestbook(request)


@app.post("/guestbook", response_class=HTMLResponse)
def sign_guestbook(
    request: Request,
    name: Annotated[str, Form()] = "",
    message: Annotated[str, Form()] = "",
):
    reject_cross_site(request)
    name, message, errors = guestbook.validate(name, message)
    if errors:
        return render_guestbook(request, errors=errors, name=name, message=message, status_code=422)
    retry_after = guestbook.add_entry(client_ip(request), name, message)
    if retry_after:
        response = render_guestbook(
            request, retry_after=retry_after, name=name, message=message, status_code=429
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
    return RedirectResponse("/guestbook", status_code=303)


@app.get("/api/hello")
def hello(name: str = "World") -> dict[str, str]:
    return {"message": f"Hello, {name}!"}
