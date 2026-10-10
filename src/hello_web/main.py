from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hello_web import guestbook

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Hello Web")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# Jinja2Templates autoescapes .html templates, so user text is always rendered inert.
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Our pages need no JavaScript, so forbid all scripts as a second line of defense against XSS.
CSP = (
    "default-src 'none'; style-src 'self'; img-src 'self'; "
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


def render_guestbook(request: Request, *, errors=(), name="", message="", status_code=200):
    context = {
        "entries": guestbook.list_entries(),
        "errors": errors,
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
    # Browsers label every request's origin; refuse forms posted from other sites (CSRF).
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        raise HTTPException(status_code=403, detail="Cross-site submissions are not allowed.")
    name, message, errors = guestbook.validate(name, message)
    if errors:
        return render_guestbook(request, errors=errors, name=name, message=message, status_code=422)
    guestbook.add_entry(name, message)
    return RedirectResponse("/guestbook", status_code=303)


@app.get("/api/hello")
def hello(name: str = "World") -> dict[str, str]:
    return {"message": f"Hello, {name}!"}
