from app.models import Role
from tests.conftest import auth_headers


def test_register_login_me_and_refresh(client):
    r = client.post("/api/auth/register", json={"email": "New@Test.io", "name": "New User", "password": "longpassword"})
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "new@test.io"
    assert r.json()["user"]["role"] == "employee"  # self-registration never grants elevated roles

    r = client.post("/api/auth/login", json={"email": "new@test.io", "password": "longpassword"})
    assert r.status_code == 200
    tokens = r.json()

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["name"] == "New User"

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200


def test_duplicate_registration_conflicts(client):
    body = {"email": "dup@test.io", "name": "Dup", "password": "longpassword"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_bad_credentials_and_tokens_rejected(client):
    auth_headers(client, "user@test.io")
    assert client.post("/api/auth/login", json={"email": "user@test.io", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@test.io", "password": "wrong-pass"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    auth_headers(client, "user@test.io")
    tokens = client.post("/api/auth/login", json={"email": "user@test.io", "password": "Password123!"}).json()
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401


def test_rbac_blocks_employee_from_admin_routes(client, employee):
    assert client.get("/api/admin/stats", headers=employee).status_code == 403
    files = {"file": ("x.md", b"# hi\n\nhello world", "text/markdown")}
    assert client.post("/api/documents", headers=employee, files=files).status_code == 403


def test_google_sso_disabled_without_config(client):
    assert client.get("/api/auth/providers").json() == {"google": False, "demo_mode": False, "daily_budget_usd": 0.0}
    assert client.get("/api/auth/google/login", follow_redirects=False).status_code == 404


def test_health_ready_metrics(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json()["status"] == "ready"
    assert "http_requests_total" in client.get("/metrics").text
    assert client.get("/health").headers["X-Content-Type-Options"] == "nosniff"


def test_agent_role_fixture(client):
    headers = auth_headers(client, "staff@test.io", Role.agent)
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "agent"
