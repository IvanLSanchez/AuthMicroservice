"""JWT (access token) revocados por logout, identificados por ``jti``."""

from sqlalchemy import Column, DateTime, String

from app.database import Base, table_args
from app.services.security import utcnow


class JwtBlacklist(Base):
    __tablename__ = "jwt_blacklist"
    __table_args__ = table_args()

    jti = Column(String, primary_key=True, nullable=False)
    expira_en = Column(DateTime, nullable=False)
    revocado_en = Column(DateTime, default=utcnow, nullable=False)
