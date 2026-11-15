"""Configuración centralizada del servicio de autenticación."""

import os
from dataclasses import dataclass
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_schema: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_expire: timedelta
    refresh_token_expire: timedelta
    seed_admin_email: str
    seed_admin_password: str


settings = Settings(
    database_url=os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/postgres"
    ),
    db_schema=os.getenv("DB_SCHEMA", "auth"),
    jwt_secret=os.getenv("JWT_SECRET", ""),
    jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    access_token_expire=timedelta(
        minutes=_parse_int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES"), 30)
    ),
    refresh_token_expire=timedelta(
        days=_parse_int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS"), 7)
    ),
    seed_admin_email=os.getenv("SEED_ADMIN_EMAIL", ""),
    seed_admin_password=os.getenv("SEED_ADMIN_PASSWORD", ""),
)
