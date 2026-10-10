import json
import logging
from itertools import count

import pytest
from fastapi.testclient import TestClient

from hello_web import guestbook, ollama
from hello_web.main import app

client = TestClient(app)
_ips = (f"10.0.0.{n}" for n in count(1))


@pytest.fixture(autouse=True)
def guestbook_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GUESTBOOK_DB", str(tmp_path / "guestbook.db"))


def sign(name: str, message: str, ip: str | None = None, **headers: str):
    """Post an entry; each call comes from a fresh client IP unless `ip` is given."""
    return TestClient(app, client=(ip or next(_ips), 50000)).post(
        "/guestbook", data={"name": name, "message": message}, headers=headers, follow_redirects=False
    )


def ask(prompt: str, ip: str | None = None, **headers: str):
    """Send a prompt to the Ollama API; each call comes from a fresh client IP unless `ip` is given."""
    return TestClient(app, client=(ip or next(_ips), 50000)).post(
        "/ollama/", json={"prompt": prompt}, headers=headers
    )


@pytest.fixture
def model_prompts(monkeypatch) -> list[str]:
    """Replace the Ollama call with an echo and return the prompts it received."""
    prompts = []

    async def generate(prompt: str) -> str:
        prompts.append(prompt)
        return f"echo: {prompt}"

    monkeypatch.setattr(ollama, "generate", generate)
    return prompts


def test_index_serves_hello_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Hello, World!" in response.text

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/x-icon"
    assert favicon.content.startswith(b"\x00\x00\x01\x00")  # ICO file signature


def test_hello_api_greets_by_name() -> None:
    assert client.get("/api/hello").json() == {"message": "Hello, World!"}
    assert client.get("/api/hello", params={"name": "Ada"}).json() == {"message": "Hello, Ada!"}


def test_guestbook_entries_are_rendered_as_text_not_html() -> None:
    assert sign("<b>Eve</b>", '<script>alert("xss")</script>').status_code == 303

    response = client.get("/guestbook")
    assert "<script>alert" not in response.text
    assert "<b>Eve" not in response.text
    assert "&lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt;" in response.text
    assert "&lt;b&gt;Eve&lt;/b&gt;" in response.text
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_rejected_input_is_echoed_back_escaped_inside_attributes() -> None:
    response = sign('"><img src=x onerror=alert(1)>', "")

    assert response.status_code == 422
    assert "Please write a message." in response.text
    assert "<img" not in response.text
    assert 'value="&#34;&gt;&lt;img src=x onerror=alert(1)&gt;"' in response.text
    assert "No entries yet" in client.get("/guestbook").text


def test_length_and_blank_limits_are_enforced_on_the_server() -> None:
    assert sign("A" * 50, "m" * 500).status_code == 303
    assert sign("A" * 51, "ok").status_code == 422
    assert sign("Bob", "m" * 501).status_code == 422
    assert sign("   ", "hi").status_code == 422
    assert sign("Bob", "\n\t \u202e").status_code == 422


def test_control_and_bidi_characters_are_stripped() -> None:
    assert sign("Mal\u202elory\x00", "line one\r\nline two\x07").status_code == 303

    page = client.get("/guestbook").text
    assert "Mallory" in page
    assert "line one\nline two" in page
    assert not any(char in page for char in "\x00\x07\r\u202e")


def test_sql_metacharacters_are_stored_literally() -> None:
    assert sign("Robert'); DROP TABLE entries;--", "hi").status_code == 303
    assert sign("Alice", "still works").status_code == 303

    page = client.get("/guestbook").text
    assert "Robert&#39;); DROP TABLE entries;--" in page
    assert "still works" in page


def test_cross_site_submissions_are_refused() -> None:
    assert sign("Eve", "spam", **{"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert sign("Me", "hello", **{"Sec-Fetch-Site": "same-origin"}).status_code == 303

    page = client.get("/guestbook").text
    assert "spam" not in page
    assert "hello" in page


def test_a_client_may_post_once_per_minute() -> None:
    assert sign("Ann", "first", ip="1.2.3.4").status_code == 303

    response = sign("Ann", "second <i>try</i>", ip="1.2.3.4")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert "reached the limit of one post per minute" in response.text
    assert "60 seconds" in response.text
    assert "second &lt;i&gt;try&lt;/i&gt;</textarea>" in response.text  # the draft is kept, escaped
    assert sign("Bob", "other client", ip="5.6.7.8").status_code == 303

    page = client.get("/guestbook").text
    assert "first" in page and "other client" in page
    assert "&lt;i&gt;try" not in page


def test_the_wait_counts_down_and_ends_after_exactly_one_minute(monkeypatch) -> None:
    now = 1_000_000.0
    monkeypatch.setattr(guestbook, "time", lambda: now)
    assert sign("Ann", "first", ip="1.2.3.4").status_code == 303

    now += 59.5
    response = sign("Ann", "too soon", ip="1.2.3.4")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert "1 second</strong>" in response.text

    now += 0.5
    assert sign("Ann", "on time", ip="1.2.3.4").status_code == 303


def test_ollama_api_sends_the_cleaned_prompt_and_returns_the_answer(model_prompts) -> None:
    response = ask("  Hi\u202e there\x00\r\n ")

    assert response.status_code == 200
    assert response.json() == {"response": "echo: Hi there"}
    assert model_prompts == ["Hi there"]


def test_ollama_api_rejects_invalid_prompts_before_using_the_limit(model_prompts) -> None:
    assert ask(" \n\u202e", ip="1.2.3.4").json() == {"detail": "Please write a prompt."}
    assert ask("x" * 1001, ip="1.2.3.4").status_code == 422
    assert ask("hi", ip="1.2.3.4", **{"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert ask("x" * 1000, ip="1.2.3.4").status_code == 200
    assert model_prompts == ["x" * 1000]


def test_ollama_api_allows_one_prompt_per_minute_separately_from_the_guestbook(model_prompts) -> None:
    assert sign("Ann", "hello", ip="1.2.3.4").status_code == 303
    assert ask("first", ip="1.2.3.4").status_code == 200

    response = ask("second", ip="1.2.3.4")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {"detail": "You've reached the limit of one post per minute."}
    assert model_prompts == ["first"]


def test_ollama_api_reports_an_unreachable_model_without_details(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")

    response = ask("hello")
    assert response.status_code == 502
    assert response.json() == {"detail": "The AI model is not available right now."}


def test_post_payloads_are_logged_as_raw_single_line_json(caplog, model_prompts) -> None:
    caplog.set_level(logging.INFO, logger="hello_web.payloads")

    sign("Eve\n2026-10-10 12:00:00 {\"forged\": true}", "", ip="9.9.9.9")
    ask("Szia\u202e!", ip="9.9.9.9")

    lines = [r.getMessage() for r in caplog.records if r.name == "hello_web.payloads"]
    assert [json.loads(line) for line in lines] == [
        {
            "client": "9.9.9.9",
            "path": "/guestbook",
            "status": 422,
            "payload": {"name": "Eve\n2026-10-10 12:00:00 {\"forged\": true}", "message": ""},
        },
        {"client": "9.9.9.9", "path": "/ollama/", "status": 200, "payload": {"prompt": "Szia\u202e!"}},
    ]
    assert not any(char in line for line in lines for char in "\n\u202e")
