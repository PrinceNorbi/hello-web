from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Hello Web")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hello, World!</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: system-ui, sans-serif;
      background: linear-gradient(135deg, #6366f1, #ec4899);
    }
    main {
      padding: 3rem 4rem; border-radius: 1.5rem; text-align: center;
      background: Canvas; box-shadow: 0 20px 50px rgb(0 0 0 / 0.25);
    }
    h1 { margin: 0 0 0.5rem; font-size: clamp(2rem, 6vw, 3.5rem); }
    p { margin: 0; opacity: 0.7; }
    a { color: #6366f1; }
  </style>
</head>
<body>
  <main>
    <h1>Hello, World! 👋</h1>
    <p>Served by FastAPI &middot; <a href="/docs">API docs</a></p>
  </main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/api/hello")
def hello(name: str = "World") -> dict[str, str]:
    return {"message": f"Hello, {name}!"}
