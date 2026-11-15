"""Gestión de refresh tokens y blacklist de JWT revocados."""

import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.model import JwtBlacklist, RefreshToken
from app.services.security import utcnow


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, usuario_id) -> str:
    """Genera un refresh token opaco, persiste su hash y devuelve el token en claro."""
    token = secrets.token_urlsafe(64)
    jti = str(uuid.uuid4())
    expira = utcnow() + settings.refresh_token_expire
    registro = RefreshToken(
        usuario_id=usuario_id,
        token_hash=_hash(token),
        jti=jti,
        expira_en=expira,
        revocado=False,
    )
    db.add(registro)
    db.commit()
    return token


def rotate_refresh_token(db: Session, token: str) -> str | None:
    """Rota un refresh token: marca el actual como revocado y emite uno nuevo.

    Devuelve el nuevo token, o ``None`` si el token presentado es inválido,
    expirado o ya fue revocado.
    """
    registro = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash(token))
        .first()
    )
    if registro is None or registro.revocado:
        return None
    if registro.expira_en < utcnow():
        return None

    registro.revocado = True
    db.commit()

    return create_refresh_token(db, registro.usuario_id)


def revoke_refresh_token(db: Session, token: str) -> None:
    """Marca un refresh token como revocado si existe."""
    registro = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash(token))
        .first()
    )
    if registro is not None:
        registro.revocado = True
        db.commit()


def is_access_token_revoked(db: Session, jti: str) -> bool:
    return db.query(JwtBlacklist).filter(JwtBlacklist.jti == jti).first() is not None


def blacklist_access_token(db: Session, jti: str, exp: datetime) -> None:
    """Agrega un ``jti`` a la blacklist hasta que expire el access token."""
    db.add(JwtBlacklist(jti=jti, expira_en=exp, revocado_en=utcnow()))
    db.commit()
