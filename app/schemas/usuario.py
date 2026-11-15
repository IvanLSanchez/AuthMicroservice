"""Schemas de gestión de operadores (solo ADMIN)."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.model.rol_usuario import RolUsuario


class CrearUsuarioDTO(BaseModel):
    email: EmailStr
    password: str
    nombre: str
    apellido: str
    rol: RolUsuario


class ActualizarUsuarioDTO(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    rol: Optional[RolUsuario] = None
    activo: Optional[bool] = None


class UsuarioDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    apellido: str
    rol: str
    activo: bool
    creado_en: datetime
    ultimo_login_en: Optional[datetime] = None
