"""Rutas de autenticación: login, refresh, logout y me."""

import math
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.model import Usuario
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UsuarioMe,
)
from app.services.limitador import limitador
from app.services.security import (
    create_access_token,
    decode_access_token,
    utcnow,
    verify_password,
)
from app.services.tokens import (
    blacklist_access_token,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

_bearer = HTTPBearer(auto_error=False)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticar usuario",
)
async def login(datos: LoginRequest, db: Session = Depends(get_db)):
    # Antes de tocar la base ni verificar la contraseña: bloqueado es bloqueado, aunque acierte.
    espera = limitador.segundos_de_espera(datos.email)
    if espera:
        minutos = math.ceil(espera / 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Demasiados intentos fallidos. Probá de nuevo en "
                f"{minutos} {'minuto' if minutos == 1 else 'minutos'}."
            ),
            headers={"Retry-After": str(espera)},
        )

    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if usuario is None or not verify_password(datos.password, usuario.password_hash):
        # También cuenta un email inexistente, con la misma respuesta: no revela qué cuentas hay.
        limitador.registrar_fallo(datos.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )
    limitador.reiniciar(datos.email)
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo",
        )

    access_token, _ = create_access_token(str(usuario.id), usuario.rol, usuario.email)
    refresh_token = create_refresh_token(db, usuario.id)

    usuario.ultimo_login_en = utcnow()
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
)
async def refresh(datos: RefreshRequest, db: Session = Depends(get_db)):
    rotado = rotate_refresh_token(db, datos.refresh_token)
    if rotado is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )
    nuevo_refresh, usuario = rotado

    access_token, _ = create_access_token(str(usuario.id), usuario.rol, usuario.email)
    return TokenResponse(access_token=access_token, refresh_token=nuevo_refresh)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
)
async def logout(
    datos: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    if datos.refresh_token:
        revoke_refresh_token(db, datos.refresh_token)

    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expira = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
                blacklist_access_token(db, jti, expira)
        except jwt.PyJWTError:
            pass

    return


@router.get(
    "/me",
    response_model=UsuarioMe,
    summary="Obtener usuario autenticado",
)
async def me(user: Usuario = Depends(get_current_user)):
    return user
