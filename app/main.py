"""Punto de entrada del AuthMicroservice."""

import ast
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validar_configuracion
from app.database import Base, SessionLocal, create_schema, engine
from app.model import JwtBlacklist, RefreshToken, Usuario  # noqa: F401
from app.routers import auth_router, usuarios_router
from app.services.security import hash_password

load_dotenv()

logger = logging.getLogger(__name__)


def _seed_admin() -> None:
    """Crea un ADMIN de desarrollo si está configurado y no existe."""
    if not settings.seed_admin_email or not settings.seed_admin_password:
        return
    db = SessionLocal()
    try:
        existente = (
            db.query(Usuario).filter(Usuario.email == settings.seed_admin_email).first()
        )
        if existente is None:
            db.add(
                Usuario(
                    email=settings.seed_admin_email,
                    nombre="Admin",
                    apellido="Sistema",
                    rol="ADMIN",
                    password_hash=hash_password(settings.seed_admin_password),
                    activo=True,
                )
            )
            db.commit()
            logger.info("Admin de seed creado: %s", settings.seed_admin_email)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validar_configuracion()  # no arranca con un JWT_SECRET vacío, corto o de ejemplo
    create_schema()
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return ["*"]
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (ValueError, SyntaxError):
        pass
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(
    title="AuthMicroservice",
    description="Autenticación de operadores internos con JWT.",
    version="1.0.0",
    lifespan=lifespan,
)

origins = _parse_origins(os.getenv("FRONTEND_LIST"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(usuarios_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
