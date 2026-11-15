"""Fixtures de pytest para los tests del AuthMicroservice."""

import os

# Configurar entorno ANTES de importar la app (usa SQLite en memoria y secreto fijo).
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
os.environ["JWT_SECRET"] = "clave-de-prueba-larga-y-segura-para-tests"
os.environ["SEED_ADMIN_EMAIL"] = ""
os.environ["SEED_ADMIN_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
