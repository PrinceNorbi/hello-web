import pytest
from fastapi.testclient import TestClient

from hello_web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def guestbook_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GUESTBOOK_DB", str(tmp_path / "guestbook.db"))


def sign(name: str, message: str, **headers: str):
    return client.post(
        "/guestbook", data={"name": name, "message": message}, headers=headers, follow_redirects=False
    )


def test_index_serves_hello_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Hello, World!" in response.text


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
