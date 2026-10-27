import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="helpdeskiq-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "STORAGE_DIR": f"{_tmp}/uploads",
    "LLM_PROVIDER": "mock",
    "LLM_FALLBACK_PROVIDERS": "",
    "EVENTS_SYNC": "true",
    "REDIS_URL": "",
    "MONGO_URL": "",
    "RATE_LIMIT_PER_MINUTE": "1000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.cache import get_cache  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.repositories.conversations import get_conversations  # noqa: E402

PASSWORD = "Password123!"


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    get_cache().clear()
    get_conversations()._data.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_user(email: str, role: Role) -> User:
    with SessionLocal() as db:
        user = User(email=email, name=email.split("@")[0], role=role, hashed_password=hash_password(PASSWORD))
        db.add(user)
        db.commit()
        return user


def auth_headers(client: TestClient, email: str, role: Role = Role.employee) -> dict:
    make_user(email, role)
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    return auth_headers(client, "admin@test.io", Role.admin)


@pytest.fixture
def agent(client):
    return auth_headers(client, "agent@test.io", Role.agent)


@pytest.fixture
def employee(client):
    return auth_headers(client, "employee@test.io", Role.employee)
