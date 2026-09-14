from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Pathforge API"


def test_login_page_sets_compatible_session_cookie():
    response = client.get("/login")
    assert response.status_code == 200
    assert "pathforge_session=" in response.headers["set-cookie"]
    assert "csrf_token" in response.text


def test_browser_session_rejects_missing_token():
    response = client.post("/api/auth/session", json={})
    assert response.status_code == 400
