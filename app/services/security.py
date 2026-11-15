"""Hashing de contraseñas y generación/validación de JWT."""

import uuid
from datetime import datetime, timezone

import bcrypt
import jwt

from app.config import settings


def utcnow() -> datetime:
    """Timestamp UTC sin tzinfo (naive), para consistencia con los ``DateTime`` de la DB."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    """Devuelve el hash bcrypt de la contraseña en texto plano."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Compara una contraseña contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(usuario_id: str, rol: str) -> tuple[str, str]:
    """Crea un access token y devuelve ``(token, jti)``.

    El ``jti`` identifica de forma única el token para poder revocarlo en logout.
    """
    jti = str(uuid.uuid4())
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "rol": rol,
        "jti": jti,
        "iat": ahora,
        "exp": ahora + settings.access_token_expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_access_token(token: str) -> dict:
    """Decodifica y valida un access token; lanza ``jwt.PyJWTError`` si es inválido."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
