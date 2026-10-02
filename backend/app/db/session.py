from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from geoalchemy2 import Geometry
from geoalchemy2.admin.dialects import sqlite as geo_sqlite

# SQLite type compilation shims for PostgreSQL-specific types
geo_sqlite.after_create = lambda *a, **kw: None
geo_sqlite.before_create = lambda *a, **kw: None
geo_sqlite.after_drop = lambda *a, **kw: None
geo_sqlite.before_drop = lambda *a, **kw: None


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


from app.core.config import settings

engine_kwargs = {"echo": False}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

if settings.DATABASE_URL.startswith("sqlite"):
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

    try:
        from app.models.audit_log import AuditLog
        AuditLog.__table__.columns["id"].autoincrement = False
    except Exception:
        pass

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
AsyncSessionLocal = async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

