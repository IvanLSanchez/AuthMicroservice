"""Operador interno autenticado en el sistema."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Uuid

from app.database import Base, table_args
from app.services.security import utcnow


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = table_args()

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    rol = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    ultimo_login_en = Column(DateTime, nullable=True)
