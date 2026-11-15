"""Tests del flujo de autenticación."""

import pytest

from app.database import SessionLocal
from app.model import Usuario
from app.services.security import hash_password


def _crear_admin(email="admin@test.com", password="secreta123", rol="ADMIN"):
    db = SessionLocal()
    try:
        usuario = Usuario(
            email=email,
            nombre="Admin",
            apellido="Test",
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


def test_login_ok(client):
    _crear_admin()
    resp = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_password_invalida(client):
    _crear_admin()
    resp = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "incorrecta"}
    )
    assert resp.status_code == 401


def test_login_usuario_inexistente(client):
    resp = client.post(
        "/auth/login", json={"email": "nadie@test.com", "password": "x"}
    )
    assert resp.status_code == 401


def test_me_con_token_valido(client):
    _crear_admin()
    login = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.com"
    assert resp.json()["rol"] == "ADMIN"


def test_me_sin_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_refresh_ok(client):
    _crear_admin()
    login = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    ).json()
    resp = client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    # El refresh token debe rotar (cambiar).
    assert body["refresh_token"] != login["refresh_token"]


def test_refresh_token_reutilizado_falla(client):
    _crear_admin()
    login = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    ).json()
    client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    # Reusar el mismo refresh token debe fallar (ya fue revocado).
    resp = client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert resp.status_code == 401


def test_logout_blacklist_access_token(client):
    _crear_admin()
    login = client.post(
        "/auth/login", json={"email": "admin@test.com", "password": "secreta123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.post(
        "/auth/logout",
        json={"refresh_token": login["refresh_token"]},
        headers=headers,
    )
    assert resp.status_code == 204
    # El access token revocado ya no debe servir.
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 401
