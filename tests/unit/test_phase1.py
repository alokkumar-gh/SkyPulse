import pytest
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.main import app
from httpx import AsyncClient, ASGITransport


def test_settings_loaded():
    assert settings.APP_NAME == "SkyPulse"
    assert settings.PORT == 8000
    assert settings.DEMO_MODE is True
    assert isinstance(settings.CORS_ORIGINS, list)


def test_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_tokens():
    user_data = {"sub": "user-12345", "role": "ANALYST"}
    token = create_access_token(user_data)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-12345"
    assert decoded["role"] == "ANALYST"
    assert decoded["type"] == "access"

    refresh_token = create_refresh_token(user_data)
    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh is not None
    assert decoded_refresh["type"] == "refresh"


@pytest.mark.asyncio
async def test_root_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "SkyPulse"
    assert data["demo_mode"] is True
