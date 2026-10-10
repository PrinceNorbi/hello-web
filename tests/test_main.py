from fastapi.testclient import TestClient

from hello_web.main import app

client = TestClient(app)


def test_index_serves_hello_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Hello, World!" in response.text


def test_hello_api_greets_by_name() -> None:
    assert client.get("/api/hello").json() == {"message": "Hello, World!"}
    assert client.get("/api/hello", params={"name": "Ada"}).json() == {"message": "Hello, Ada!"}
