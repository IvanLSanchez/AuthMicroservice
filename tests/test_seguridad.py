"""Tests de los endurecimientos de seguridad: usuarios inactivos, claims y secreto."""

import jwt
import pytest

from app.config import Settings, validar_configuracion
from app.database import SessionLocal
from app.model import RefreshToken, Usuario
from app.services.security import hash_password


def _crear_usuario(email, rol="ADMIN", password="secreta123"):
    db = SessionLocal()
    try:
        usuario = Usuario(
            email=email,
            nombre="Nora",
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


def _login(client, email, password="secreta123"):
    return client.post("/auth/login", json={"email": email, "password": password}).json()


def _desactivar(client, admin_login, usuario_id):
    return client.patch(
        f"/auth/usuarios/{usuario_id}",
        json={"activo": False},
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )


def test_refresh_falla_si_el_usuario_esta_inactivo(client):
    _crear_usuario("admin@test.com")
    op = _crear_usuario("op@test.com", rol="TELEMARKETING")
    login_op = _login(client, "op@test.com")

    # Se desactiva directo en la base (sin pasar por la API) para aislar el chequeo del refresh.
    db = SessionLocal()
    try:
        db.query(Usuario).filter(Usuario.id == op.id).update({"activo": False})
        db.commit()
    finally:
        db.close()

    resp = client.post("/auth/refresh", json={"refresh_token": login_op["refresh_token"]})
    assert resp.status_code == 401


def test_desactivar_usuario_revoca_sus_refresh_tokens(client):
    _crear_usuario("admin@test.com")
    op = _crear_usuario("op@test.com", rol="TELEMARKETING")
    login_admin = _login(client, "admin@test.com")
    _login(client, "op@test.com")
    _login(client, "op@test.com")

    assert _desactivar(client, login_admin, op.id).status_code == 200

    db = SessionLocal()
    try:
        tokens = db.query(RefreshToken).filter(RefreshToken.usuario_id == op.id).all()
        assert len(tokens) == 2
        assert all(t.revocado for t in tokens)
    finally:
        db.close()


def test_reactivar_usuario_no_toca_tokens_de_otros(client):
    _crear_usuario("admin@test.com")
    op = _crear_usuario("op@test.com", rol="TELEMARKETING")
    login_admin = _login(client, "admin@test.com")
    _login(client, "op@test.com")

    _desactivar(client, login_admin, op.id)

    # El refresh del admin sigue sirviendo.
    resp = client.post("/auth/refresh", json={"refresh_token": login_admin["refresh_token"]})
    assert resp.status_code == 200


def test_el_access_token_lleva_email(client):
    _crear_usuario("admin@test.com")
    login = _login(client, "admin@test.com")
    claims = jwt.decode(
        login["access_token"], options={"verify_signature": False}
    )
    assert claims["email"] == "admin@test.com"
    assert claims["rol"] == "ADMIN"
    assert claims["sub"]


def test_el_refresh_tambien_emite_token_con_email(client):
    _crear_usuario("admin@test.com")
    login = _login(client, "admin@test.com")
    resp = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]}).json()
    claims = jwt.decode(resp["access_token"], options={"verify_signature": False})
    assert claims["email"] == "admin@test.com"


def _settings(**cambios):
    base = dict(
        database_url="postgresql://x",
        db_schema="auth",
        jwt_secret="x" * 40,
        jwt_algorithm="HS256",
        access_token_expire=__import__("datetime").timedelta(minutes=15),
        refresh_token_expire=__import__("datetime").timedelta(days=7),
        seed_admin_email="",
        seed_admin_password="",
    )
    base.update(cambios)
    return Settings(**base)


def test_no_arranca_sin_secreto_jwt():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validar_configuracion(_settings(jwt_secret=""))


def test_no_arranca_con_secreto_corto():
    with pytest.raises(RuntimeError, match="32"):
        validar_configuracion(_settings(jwt_secret="corto"))


def test_no_arranca_con_el_secreto_del_ejemplo():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validar_configuracion(
            _settings(jwt_secret="cambiar-por-una-clave-secreta-larga-y-aleatoria")
        )


def test_arranca_con_un_secreto_valido():
    validar_configuracion(_settings())  # no lanza


def test_el_vencimiento_por_defecto_es_de_15_minutos():
    from app import config

    assert config.DEFAULT_ACCESS_TOKEN_MINUTES == 15
