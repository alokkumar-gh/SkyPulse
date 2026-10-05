"""
Custom database types for seamless SQLite and PostgreSQL interoperability.
Guarantees consistent UUID handling across SQLite (as hyphenated TEXT or INT)
and PostgreSQL (as native UUID).
"""
import uuid
from typing import Any, Optional
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """
    Platform-independent GUID/UUID type.
    Uses PostgreSQL's native UUID type, otherwise uses CHAR(36) with hyphens.
    Coerces legacy int representations (e.g. 8 -> 00000000-0000-0000-0000-000000000008) seamlessly.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, int):
            return str(uuid.UUID(int=value))
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, TypeError):
            return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, int):
            return uuid.UUID(int=value)
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return None
