import asyncio
import uuid
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport

from geoalchemy2.admin.dialects import sqlite as geo_sqlite
geo_sqlite.after_create = lambda *a, **kw: None
geo_sqlite.before_create = lambda *a, **kw: None
geo_sqlite.after_drop = lambda *a, **kw: None
geo_sqlite.before_drop = lambda *a, **kw: None

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from geoalchemy2 import Geometry
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import get_password_hash, create_access_token


from app.models.audit_log import AuditLog
AuditLog.__table__.columns["id"].autoincrement = False

# Phase 6 models
from app.models.alert import Alert  # noqa: F401 — ensures table is in metadata


# SQLite type compilation shims for PostgreSQL-specific types
@compiles(ARRAY, "sqlite")
def compile_array(type_, compiler, **kw):
    return "TEXT"


@compiles(INET, "sqlite")
def compile_inet(type_, compiler, **kw):
    return "TEXT"


@compiles(JSONB, "sqlite")
def compile_jsonb(type_, compiler, **kw):
    return "JSON"


@compiles(Vector, "sqlite")
def compile_vector(type_, compiler, **kw):
    return "TEXT"


@compiles(Geometry, "sqlite")
def compile_geometry(type_, compiler, **kw):
    return "TEXT"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    db_id = uuid.uuid4().hex
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:memdb_{db_id}?mode=memory&cache=shared&uri=true",
        echo=False,
    )
    from sqlalchemy import event
    from shapely import wkt

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_conn, record):
        def _as_ewkb(val):
            if not val:
                return None
            try:
                if isinstance(val, str):
                    if ";" in val:
                        val = val.split(";", 1)[1]
                    geom = wkt.loads(val)
                    return geom.wkb_hex
            except Exception:
                pass
            return "010100000000000000002052400000000000003740"

        def _identity(*args):
            return args[0] if args else None

        dbapi_conn.create_function("AsEWKB", 1, _as_ewkb)
        dbapi_conn.create_function("ST_AsEWKB", 1, _as_ewkb)

        for fn_name in [
            "AsBinary", "GeomFromEWKB", "GeomFromEWKT",
            "GeomFromText", "ST_GeomFromText", "ST_MakePoint",
            "ST_SetSRID", "ST_DWithin", "ST_Distance", "geography"
        ]:
            try:
                dbapi_conn.create_function(fn_name, -1, _identity)
            except Exception:
                pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_citizen(db_session: AsyncSession) -> User:
    user = User(
        email="citizen@skypulse.gov.in",
        password_hash=get_password_hash("Password123!"),
        display_name="Citizen User",
        role=UserRole.CITIZEN.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_analyst(db_session: AsyncSession) -> User:
    user = User(
        email="analyst@skypulse.gov.in",
        password_hash=get_password_hash("Password123!"),
        display_name="Analyst User",
        role=UserRole.ANALYST.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@skypulse.gov.in",
        password_hash=get_password_hash("Password123!"),
        display_name="Admin User",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers():
    def _headers(user: User):
        token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        return {"Authorization": f"Bearer {token}"}
    return _headers


@pytest_asyncio.fixture(scope="function")
async def test_government(db_session: AsyncSession) -> User:
    user = User(
        email="govt@skypulse.gov.in",
        password_hash=get_password_hash("Password123!"),
        display_name="Government User",
        role=UserRole.GOVERNMENT.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
