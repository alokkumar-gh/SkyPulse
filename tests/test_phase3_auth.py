import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "password": "SecurePassword123!",
        "display_name": "New SkyPulse User",
        "phone_number": "+919876543210",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "CITIZEN"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_citizen: User):
    payload = {
        "email": test_citizen.email,
        "password": "AnotherPassword123!",
        "display_name": "Duplicate User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["error"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_register_invalid_password(client: AsyncClient):
    payload = {
        "email": "shortpw@example.com",
        "password": "short",
        "display_name": "Short PW User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_citizen: User):
    payload = {
        "email": test_citizen.email,
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_citizen.email
    assert data["user"]["role"] == "CITIZEN"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_citizen: User):
    payload = {
        "email": test_citizen.email,
        "password": "WrongPassword!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, test_citizen: User, auth_headers):
    headers = auth_headers(test_citizen)
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_citizen.email
    assert data["display_name"] == test_citizen.display_name


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_rbac_admin_restriction(
    client: AsyncClient, test_citizen: User, test_admin: User, auth_headers
):
    # Citizen trying to access admin endpoint
    citizen_hdrs = auth_headers(test_citizen)
    res_citizen = await client.get("/api/v1/admin/users", headers=citizen_hdrs)
    assert res_citizen.status_code == 403
    assert res_citizen.json()["error"] == "FORBIDDEN"

    # Admin accessing admin endpoint
    admin_hdrs = auth_headers(test_admin)
    res_admin = await client.get("/api/v1/admin/users", headers=admin_hdrs)
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list)
