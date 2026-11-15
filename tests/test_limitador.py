"""Límite de intentos de login: tras varios fallos seguidos hay que esperar antes de probar de nuevo."""

import pytest

from app.config import Settings, settings
from app.database import SessionLocal
from app.model import Usuario
from app.services.limitador import LimitadorIntentos, limitador
from app.services.security import hash_password


class Reloj:
    """Reloj falso para no esperar 5 minutos de verdad."""

    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora

    def avanzar(self, segundos):
        self.ahora += segundos


@pytest.fixture
def reloj():
    return Reloj()


def nuevo(reloj, **kw):
    base = dict(max_intentos=5, ventana_segundos=300, bloqueo_segundos=300, reloj=reloj)
    base.update(kw)
    return LimitadorIntentos(**base)


# ----------------------------------------------------------------- el limitador solo


def test_sin_fallos_no_hay_espera(reloj):
    assert nuevo(reloj).segundos_de_espera("ana@test.com") == 0


def test_los_primeros_fallos_no_bloquean(reloj):
    lim = nuevo(reloj)
    for _ in range(4):
        lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 0


def test_al_llegar_al_maximo_hay_que_esperar_5_minutos(reloj):
    lim = nuevo(reloj)
    for _ in range(5):
        lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 300


def test_la_espera_baja_con_el_tiempo_y_termina(reloj):
    lim = nuevo(reloj)
    for _ in range(5):
        lim.registrar_fallo("ana@test.com")
    reloj.avanzar(100)
    assert lim.segundos_de_espera("ana@test.com") == 200
    reloj.avanzar(200)
    assert lim.segundos_de_espera("ana@test.com") == 0


def test_cumplida_la_espera_se_vuelve_a_empezar_de_cero(reloj):
    lim = nuevo(reloj)
    for _ in range(5):
        lim.registrar_fallo("ana@test.com")
    reloj.avanzar(301)
    assert lim.segundos_de_espera("ana@test.com") == 0
    for _ in range(4):  # otra vez 4 fallos: todavía no se bloquea
        lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 0


def test_insistir_durante_el_bloqueo_no_lo_extiende(reloj):
    lim = nuevo(reloj)
    for _ in range(5):
        lim.registrar_fallo("ana@test.com")
    reloj.avanzar(100)
    for _ in range(10):
        lim.registrar_fallo("ana@test.com")
    # Si lo extendiera, un atacante dejaría a la víctima afuera para siempre.
    assert lim.segundos_de_espera("ana@test.com") == 200


def test_los_fallos_viejos_no_se_acumulan(reloj):
    lim = nuevo(reloj)
    for _ in range(4):
        lim.registrar_fallo("ana@test.com")
    reloj.avanzar(301)  # fuera de la ventana
    lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 0


def test_un_login_correcto_borra_los_fallos(reloj):
    lim = nuevo(reloj)
    for _ in range(4):
        lim.registrar_fallo("ana@test.com")
    lim.reiniciar("ana@test.com")
    for _ in range(4):
        lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 0


def test_cada_email_cuenta_por_separado(reloj):
    lim = nuevo(reloj)
    for _ in range(5):
        lim.registrar_fallo("ana@test.com")
    assert lim.segundos_de_espera("ana@test.com") == 300
    assert lim.segundos_de_espera("beto@test.com") == 0


def test_no_distingue_mayusculas_ni_espacios(reloj):
    lim = nuevo(reloj)
    for correo in ["Ana@Test.com", " ana@test.com", "ANA@TEST.COM", "ana@test.com", "ana@test.com "]:
        lim.registrar_fallo(correo)
    assert lim.segundos_de_espera("ana@test.com") == 300


def test_la_memoria_tiene_un_tope(reloj):
    lim = nuevo(reloj, max_registros=100)
    for i in range(1000):
        lim.registrar_fallo(f"inventado{i}@test.com")
    assert lim.cantidad_de_registros() <= 100


def test_el_tope_prefiere_descartar_registros_vencidos(reloj):
    lim = nuevo(reloj, max_registros=3)
    for _ in range(5):
        lim.registrar_fallo("bloqueada@test.com")
    for i in range(3):
        lim.registrar_fallo(f"otra{i}@test.com")
    # El bloqueo vigente no se pierde por llenar la memoria con otros emails.
    assert lim.segundos_de_espera("bloqueada@test.com") > 0


def test_la_configuracion_por_defecto_es_de_5_intentos_y_5_minutos():
    assert settings.login_max_intentos == 5
    assert settings.login_bloqueo_segundos == 300
    assert Settings.__dataclass_fields__["login_max_intentos"].default == 5


# ------------------------------------------------------------------ por el endpoint


def _crear(email="ana@test.com", password="secreta123"):
    db = SessionLocal()
    try:
        db.add(
            Usuario(
                email=email,
                nombre="Ana",
                apellido="Test",
                rol="TELEMARKETING",
                password_hash=hash_password(password),
                activo=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _login(client, email="ana@test.com", password="secreta123"):
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture(autouse=True)
def _limitador_limpio(reloj):
    limitador.reiniciar_todo()
    original = limitador.reloj
    limitador.reloj = reloj
    yield
    limitador.reloj = original
    limitador.reiniciar_todo()


def test_despues_de_5_fallos_el_login_responde_429_con_retry_after(client, reloj):
    _crear()
    for _ in range(5):
        assert _login(client, password="mala").status_code == 401
    r = _login(client, password="mala")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "300"
    assert "5 minutos" in r.json()["detail"]


def test_durante_el_bloqueo_ni_la_contrasena_correcta_entra(client):
    _crear()
    for _ in range(5):
        _login(client, password="mala")
    assert _login(client).status_code == 429  # si entrara, se podría seguir adivinando


def test_pasados_5_minutos_se_puede_volver_a_intentar(client, reloj):
    _crear()
    for _ in range(5):
        _login(client, password="mala")
    reloj.avanzar(301)
    assert _login(client).status_code == 200


def test_un_email_inexistente_tambien_se_bloquea_sin_revelar_que_no_existe(client):
    for _ in range(5):
        assert _login(client, email="nadie@test.com", password="x").status_code == 401
    r = _login(client, email="nadie@test.com", password="x")
    assert r.status_code == 429
    assert r.json()["detail"] == _bloqueo_de_un_usuario_real(client)


def _bloqueo_de_un_usuario_real(client):
    _crear("real@test.com")
    for _ in range(5):
        _login(client, email="real@test.com", password="x")
    return _login(client, email="real@test.com", password="x").json()["detail"]


def test_un_login_correcto_antes_del_limite_borra_los_fallos(client):
    _crear()
    for _ in range(4):
        _login(client, password="mala")
    assert _login(client).status_code == 200
    for _ in range(4):
        _login(client, password="mala")
    assert _login(client).status_code == 200


def test_otro_usuario_no_se_ve_afectado(client):
    _crear("ana@test.com")
    _crear("beto@test.com")
    for _ in range(5):
        _login(client, email="ana@test.com", password="mala")
    assert _login(client, email="ana@test.com").status_code == 429
    assert _login(client, email="beto@test.com").status_code == 200


def test_el_usuario_inactivo_con_la_clave_correcta_no_cuenta_como_fallo(client):
    _crear()
    db = SessionLocal()
    try:
        db.query(Usuario).update({"activo": False})
        db.commit()
    finally:
        db.close()
    for _ in range(10):
        assert _login(client).status_code == 401
