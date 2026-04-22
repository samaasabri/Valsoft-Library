import os
import tempfile
from pathlib import Path

import pytest

# Point the app at an isolated SQLite file & deterministic settings BEFORE importing the app.
_tmp_dir = tempfile.mkdtemp(prefix="lib_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp_dir) / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_EMAILS"] = "admin@test.com"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.pop("GEMINI_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield


@pytest.fixture
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client(client):
    client.post("/auth/dev", data={"email": "admin@test.com", "name": "Admin"}, follow_redirects=False)
    return client


@pytest.fixture
def member_client(client):
    client.post("/auth/dev", data={"email": "member@test.com", "name": "Member"}, follow_redirects=False)
    return client
