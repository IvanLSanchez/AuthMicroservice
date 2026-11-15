"""Tests de gestión de operadores y control de roles."""

from app.database import SessionLocal
from app.model import Usuario
from app.services.security import hash_password


def _crear_usuario(email, rol, password="secreta123"):
    db = SessionLocal()
    try:
        usuario = Usuario(
            email=email,
            nombre="N",
            apellido="A",
            rol=rol,
            password_hash=hash_password(password),
            activo=True,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario
    finally:
        db.close()


def _token_admin(client):
    _crear_usuario("admin@test.com", "ADMIN")
    return client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    ).json()["access_token"]


def test_crear_usuario_solo_admin(client):
    token = _token_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/auth/usuarios",
        json={
            "email": "asesor@test.com",
            "password": "clave123",
            "nombre": "Juan",
            "apellido": "Perez",
            "rol": "ASESOR",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["rol"] == "ASESOR"


def test_crear_usuario_sin_admin_forbidden(client):
    _crear_usuario("asesor@test.com", "ASESOR")
    token = client.post(
        "/auth/login", json={"email": "asesor@test.com", "password": "secreta123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/auth/usuarios",
        json={
            "email": "otro@test.com",
            "password": "clave123",
            "nombre": "X",
            "apellido": "Y",
            "rol": "ASESOR",
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_listar_usuarios(client):
    token = _token_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/auth/usuarios", headers=headers)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "admin@test.com" in emails


def test_email_duplicado_conflict(client):
    token = _token_admin(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "email": "dup@test.com",
        "password": "clave123",
        "nombre": "X",
        "apellido": "Y",
        "rol": "ASESOR",
    }
    assert client.post("/auth/usuarios", json=payload, headers=headers).status_code == 201
    resp = client.post("/auth/usuarios", json=payload, headers=headers)
    assert resp.status_code == 409
