"""Configuración centralizada del servicio de autenticación."""

import os
from dataclasses import dataclass
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


# Access token corto: el orquestador lo valida localmente y, ante un logout, lo invalida en el acto;
# este vencimiento es la red de seguridad (por ejemplo, si el logout no pasó por el orquestador).
DEFAULT_ACCESS_TOKEN_MINUTES = 15

# HS256 con una clave corta se puede adivinar por fuerza bruta.
MIN_JWT_SECRET_LENGTH = 32
_SECRETOS_DE_EJEMPLO = {"cambiar-por-una-clave-secreta-larga-y-aleatoria"}


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
        minutes=_parse_int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES"), DEFAULT_ACCESS_TOKEN_MINUTES
        )
    ),
    refresh_token_expire=timedelta(
        days=_parse_int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS"), 7)
    ),
    seed_admin_email=os.getenv("SEED_ADMIN_EMAIL", ""),
    seed_admin_password=os.getenv("SEED_ADMIN_PASSWORD", ""),
)


def validar_configuracion(s: Settings = settings) -> None:
    """Falla al arrancar si el secreto de los JWT falta, es corto o es el del ejemplo.

    Sin esto el servicio firmaría los tokens con una clave vacía o conocida.
    """
    if not s.jwt_secret or s.jwt_secret in _SECRETOS_DE_EJEMPLO:
        raise RuntimeError(
            "JWT_SECRET no está configurado (o es el valor del ejemplo). "
            "Definí una clave aleatoria de al menos "
            f"{MIN_JWT_SECRET_LENGTH} caracteres, por ejemplo: openssl rand -base64 48"
        )
    if len(s.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET es demasiado corto: tiene {len(s.jwt_secret)} caracteres y "
            f"se necesitan al menos {MIN_JWT_SECRET_LENGTH}."
        )
