import os
import tempfile
from pathlib import Path
import asyncio

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.gettempdir()) / 'liveslide-api-tests.db'}")
os.environ.setdefault("PHOTO_STORAGE_DIR", str(Path(tempfile.gettempdir()) / "liveslide-api-test-photos"))

import pytest
import httpx

from liveslide_api.db import Base, SessionLocal, engine
from liveslide_api.main import _protect_audit_table, app
from liveslide_api.models import Cell, User
from liveslide_api.security import hash_password


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _protect_audit_table()
    session = SessionLocal()
    for email, role in (("officer@example.test", "officer"),
                        ("volunteer@example.test", "volunteer"),
                        ("other@example.test", "volunteer"),
                        ("admin@example.test", "admin")):
        session.add(User(email=email, role=role, display_name=email,
                         password_hash=hash_password("test-password")))
    session.add(Cell(cell_id="AS-0000-0000", state="AS", row=0, col=0,
                     min_lon=91.6, min_lat=26.0, max_lon=91.61, max_lat=26.01,
                     synthetic=True))
    session.commit()
    session.close()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    class SyncASGIClient:
        def request(self, method, url, **kwargs):
            async def send():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
                    return await async_client.request(method, url, **kwargs)
            return asyncio.run(send())

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

    yield SyncASGIClient()


def login(client, email="officer@example.test"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "test-password"})
    assert response.status_code == 200
    return response.json()["access_token"]
