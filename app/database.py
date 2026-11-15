"""Conexión a Supabase (PostgreSQL) usando el schema compartido ``auth``."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

# SQLite (tests) no soporta schemas ni pooling de conexiones.
_IS_SQLITE = DATABASE_URL.startswith("sqlite")


def table_args() -> dict:
    """``__table_args__`` común para los modelos: schema solo en Postgres."""
    if _IS_SQLITE:
        return {}
    return {"schema": settings.db_schema}


engine_args: dict = {}
if _IS_SQLITE:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    # Pool chico: el pooler de sesión de Supabase limita la cantidad de clientes.
    # Mismo patrón que los demás microservicios.
    engine_args.update(
        pool_size=3,
        max_overflow=0,
        pool_recycle=180,
        pool_pre_ping=True,
        pool_timeout=10,
    )

engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
