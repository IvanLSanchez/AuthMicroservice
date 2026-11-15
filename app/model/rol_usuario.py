"""Roles de los operadores internos del CRM."""

from enum import Enum


class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    ASESOR = "ASESOR"
    COMERCIAL = "COMERCIAL"
    TELEMARKETING = "TELEMARKETING"
