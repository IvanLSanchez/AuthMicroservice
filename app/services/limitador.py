"""Límite de intentos de login: frena la fuerza bruta contra una cuenta.

Después de ``max_intentos`` fallos dentro de la ventana, el email queda bloqueado
``bloqueo_segundos`` (5 minutos por defecto). Reglas:

- Se cuenta **por email**, no por IP: detrás del orquestador todos los pedidos llegan desde
  la IP del gateway, y un límite por IP dejaría afuera a todos por culpa de uno.
- También cuenta un email que no existe, y la respuesta es la misma, para no revelar qué
  cuentas hay.
- Durante el bloqueo ni la contraseña correcta entra (si no, se podría seguir adivinando), y
  insistir **no** lo extiende (si no, un atacante dejaría afuera a la víctima para siempre).
- Un login correcto borra los fallos.

Limitación: el estado vive en la memoria del proceso. Con varias réplicas, cada una cuenta por
su lado, y un reinicio lo borra. Para un TP con una réplica alcanza.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable

from app.config import settings


@dataclass
class _Registro:
    fallos: int
    desde: float  # momento del primer fallo de la ventana
    bloqueado_hasta: float = 0.0


def _clave(email: str) -> str:
    return email.strip().lower()


class LimitadorIntentos:
    def __init__(
        self,
        max_intentos: int,
        ventana_segundos: int,
        bloqueo_segundos: int,
        reloj: Callable[[], float] = time.monotonic,
        max_registros: int = 10_000,
    ) -> None:
        self.max_intentos = max_intentos
        self.ventana_segundos = ventana_segundos
        self.bloqueo_segundos = bloqueo_segundos
        self.reloj = reloj
        self.max_registros = max_registros
        self._registros: dict[str, _Registro] = {}

    def segundos_de_espera(self, email: str) -> int:
        """0 si puede intentar; si no, cuántos segundos faltan para que se le levante el bloqueo."""
        registro = self._registros.get(_clave(email))
        if registro is None:
            return 0
        ahora = self.reloj()
        if registro.bloqueado_hasta > ahora:
            return math.ceil(registro.bloqueado_hasta - ahora)
        if registro.bloqueado_hasta:
            # Cumplió la espera: se vuelve a empezar de cero.
            del self._registros[_clave(email)]
        return 0

    def registrar_fallo(self, email: str) -> None:
        clave = _clave(email)
        ahora = self.reloj()
        registro = self._registros.get(clave)

        if registro is not None and registro.bloqueado_hasta > ahora:
            return  # ya está bloqueado: insistir no extiende la espera
        if registro is None or registro.bloqueado_hasta or ahora - registro.desde > self.ventana_segundos:
            self._hacer_lugar()
            registro = self._registros[clave] = _Registro(fallos=0, desde=ahora)

        registro.fallos += 1
        if registro.fallos >= self.max_intentos:
            registro.bloqueado_hasta = ahora + self.bloqueo_segundos

    def reiniciar(self, email: str) -> None:
        self._registros.pop(_clave(email), None)

    def reiniciar_todo(self) -> None:
        self._registros.clear()

    def cantidad_de_registros(self) -> int:
        return len(self._registros)

    def _hacer_lugar(self) -> None:
        """Tope de memoria: alguien podría mandar millones de emails inventados."""
        if len(self._registros) < self.max_registros:
            return
        ahora = self.reloj()
        # Primero se descartan los que ya no cuentan (ventana vencida o bloqueo cumplido)...
        for clave in [
            c
            for c, r in self._registros.items()
            if (r.bloqueado_hasta and r.bloqueado_hasta <= ahora)
            or (not r.bloqueado_hasta and ahora - r.desde > self.ventana_segundos)
        ]:
            del self._registros[clave]
        # ...y si sigue lleno, los fallos sueltos más viejos. Los bloqueos vigentes se conservan.
        while len(self._registros) >= self.max_registros:
            sueltos = [(r.desde, c) for c, r in self._registros.items() if not r.bloqueado_hasta]
            if not sueltos:
                break
            del self._registros[min(sueltos)[1]]


limitador = LimitadorIntentos(
    max_intentos=settings.login_max_intentos,
    ventana_segundos=settings.login_ventana_segundos,
    bloqueo_segundos=settings.login_bloqueo_segundos,
)
