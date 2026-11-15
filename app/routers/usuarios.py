"""Gestión de operadores (solo ADMIN)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.model import RolUsuario, Usuario
from app.schemas import ActualizarUsuarioDTO, CrearUsuarioDTO, UsuarioDTO
from app.services.security import hash_password
from app.services.tokens import revoke_all_refresh_tokens

router = APIRouter(prefix="/auth/usuarios", tags=["Usuarios"])


@router.post(
    "",
    response_model=UsuarioDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear operador",
)
async def crear_usuario(
    datos: CrearUsuarioDTO,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN.value)),
):
    existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )

    nuevo = Usuario(
        email=datos.email,
        nombre=datos.nombre,
        apellido=datos.apellido,
        rol=datos.rol.value,
        password_hash=hash_password(datos.password),
        activo=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get(
    "",
    response_model=list[UsuarioDTO],
    summary="Listar operadores",
)
async def listar_usuarios(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN.value)),
):
    return db.query(Usuario).order_by(Usuario.creado_en).all()


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioDTO,
    summary="Actualizar operador",
)
async def actualizar_usuario(
    usuario_id: str,
    datos: ActualizarUsuarioDTO,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN.value)),
):
    usuario = db.query(Usuario).filter(Usuario.id == uuid.UUID(usuario_id)).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.apellido is not None:
        usuario.apellido = datos.apellido
    if datos.rol is not None:
        usuario.rol = datos.rol.value
    if datos.activo is not None:
        usuario.activo = datos.activo

    db.commit()
    if datos.activo is False:
        # Un operador desactivado no puede renovar su sesión con tokens que ya tenía.
        revoke_all_refresh_tokens(db, usuario.id)
    db.refresh(usuario)
    return usuario
