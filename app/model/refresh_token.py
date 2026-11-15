"""Refresh token persistido (solo se guarda el hash, nunca el token en claro)."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Uuid

from app.database import Base, table_args
from app.model.usuario import Usuario
from app.services.security import utcnow


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = table_args()

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, nullable=False)
    usuario_id = Column(
        Uuid,
        ForeignKey(Usuario.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String, unique=True, nullable=False, index=True)
    jti = Column(String, unique=True, nullable=False, index=True)
    expira_en = Column(DateTime, nullable=False)
    revocado = Column(Boolean, default=False, nullable=False)
    creado_en = Column(DateTime, default=utcnow, nullable=False)
