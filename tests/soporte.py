"""Herramientas comunes de las pruebas: ficha de cada caso, pasos con evidencia, cliente de la API y 2FA."""
import base64
import hashlib
import hmac
import json
import os
import struct
import time
from contextlib import contextmanager

import pytest
import requests

SUITES = ["smoke", "sanity", "regression", "integration", "e2e", "performance", "estres", "soak"]


def caso(id, nombre, *, suites, tipo="funcional", modulo="", objetivo="", precondiciones="", datos="",
         resultado_esperado=""):
    """Ficha del caso de prueba. Se usa en el catálogo de la web y en el informe PDF."""
    def deco(fn):
        fn._caso = dict(id=id, nombre=nombre, suites=list(suites), tipo=tipo, modulo=modulo, objetivo=objetivo,
                        precondiciones=precondiciones, datos=datos, resultado_esperado=resultado_esperado)
        for s in suites:
            fn = getattr(pytest.mark, s)(fn)
        return fn
    return deco


class FalloInfraestructura(Exception):
    """El sistema bajo prueba no responde: no es un fallo funcional, es del entorno."""


class Registro:
    """Guarda los pasos de un caso: acción, lo observado, estado, duración y captura (en E2E)."""

    def __init__(self, carpeta_capturas, caso_id=""):
        self.pasos = []
        self.page = None
        self.carpeta = carpeta_capturas
        self.caso_id = caso_id
        self._vivo = os.path.join(os.path.dirname(os.path.dirname(carpeta_capturas)), "vivo.json")
        self.presentacion = False      # modo presentación: rótulo del paso en el navegador (lo activa conftest)

    def rotular(self, texto):
        """Modo presentación: muestra en el navegador qué paso se está ejecutando.
        El texto va en un pseudo-elemento CSS, así ningún locator de las pruebas puede confundirlo con el panel."""
        if not (self.presentacion and self.page):
            return
        try:
            self.page.context.add_init_script(f"window.__qaTexto = {json.dumps(texto)};")   # sobrevive a la navegación
            self.page.evaluate("t => { window.__qaTexto = t; window.__qa && window.__qa.montar(); }", texto)
        except Exception:  # noqa: BLE001
            pass

    def _limpiar_pantalla(self, si):
        """Quita (o repone) el rótulo y el resaltado, para que la captura de evidencia muestre solo el panel."""
        if self.presentacion and self.page:
            try:
                self.page.evaluate("si => window.__qa && window.__qa.ocultar(si)", si)
            except Exception:  # noqa: BLE001
                pass

    def avisar(self, texto):
        """Publica un aviso del paso en curso (p. ej. la cuenta regresiva del 2FA) en la web y en el rótulo."""
        if self.pasos:
            p = self.pasos[-1]
            p["espera"] = texto
            estado, p["estado"] = p["estado"], "EN CURSO"
            self._publicar()
            p["estado"] = estado
            self.rotular(f"{self.caso_id} · Paso {p['n']}: {texto}")

    def _publicar(self):
        """Deja los pasos del caso en curso en vivo.json: la web los muestra mientras la prueba corre."""
        try:
            tmp = self._vivo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"id": self.caso_id, "pasos": self.pasos}, fh, ensure_ascii=False)
            os.replace(tmp, self._vivo)
        except OSError:
            pass

    def _captura(self, n, sufijo=""):
        if self.page is None:
            return None
        os.makedirs(self.carpeta, exist_ok=True)
        ruta = os.path.join(self.carpeta, f"paso{n:02d}{sufijo}.jpg")
        self._limpiar_pantalla(True)
        try:
            self.page.screenshot(path=ruta, type="jpeg", quality=72)
            return ruta
        except Exception:  # noqa: BLE001
            return None
        finally:
            self._limpiar_pantalla(False)

    @contextmanager
    def paso(self, accion):
        p = {"n": len(self.pasos) + 1, "accion": accion, "observado": "", "estado": "PASS"}
        self.pasos.append(p)
        p["estado"] = "EN CURSO"
        self._publicar()
        p["estado"] = "PASS"
        self.rotular(f"{self.caso_id} · Paso {p['n']}: {accion}")
        t0 = time.time()
        try:
            yield p
        except BaseException as e:
            p["estado"] = "FAIL" if isinstance(e, AssertionError) else "ERROR"
            p["observado"] = (p["observado"] + " | " if p["observado"] else "") + _texto_error(e)
            if "waiting for" in str(e):     # elemento que no apareció: lo usa la autocuración con IA
                p["detalle_error"] = str(e)[:1500]
            p["captura"] = self._captura(p["n"], "-fallo")
            raise
        finally:
            p["ms"] = round((time.time() - t0) * 1000)
            p.pop("espera", None)
            if p["estado"] == "PASS":
                p["captura"] = self._captura(p["n"])
            self._publicar()


def _texto_error(e):
    t = str(e).strip().split("\n")[0][:300]
    return f"{type(e).__name__}: {t}" if t else type(e).__name__


class API:
    """Cliente HTTP de SIBIO-RFID. Si el servidor no responde, lanza FalloInfraestructura."""

    def __init__(self, base):
        self.base = base.rstrip("/")
        self.s = requests.Session()

    def llamar(self, metodo, ruta, token=None, recinto=None, clave_lector=None, **kw):
        h = kw.pop("headers", {})
        if token:
            h["Authorization"] = f"Bearer {token}"
        if recinto:
            h["X-Recinto"] = str(recinto)
        if clave_lector:
            h["X-API-Key"] = clave_lector
        t0 = time.time()
        try:
            r = self.s.request(metodo, self.base + ruta, headers=h, timeout=20, **kw)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise FalloInfraestructura(f"SIBIO-RFID no responde en {self.base} ({type(e).__name__})") from e
        r.ms = round((time.time() - t0) * 1000)
        try:
            r.datos = r.json()
        except ValueError:
            r.datos = {}
        return r

    def login(self, usuario, clave):
        r = self.llamar("POST", "/api/auth/login", json={"username": usuario, "password": clave})
        return r.datos.get("token") if r.status_code == 200 else None


# ---------------------------------------------------------------- verificación en dos pasos (TOTP)
_ARCHIVO_PASO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reportes", ".ultimo_paso_2fa")


def totp(secreto, paso):
    """Código de 6 dígitos de Google Authenticator (RFC 6238, SHA-1, 30 s)."""
    secreto = secreto.replace(" ", "").upper()
    clave = base64.b32decode(secreto + "=" * (-len(secreto) % 8))
    r = hmac.new(clave, struct.pack(">Q", paso), hashlib.sha1).digest()
    d = r[-1] & 0x0F
    return str((struct.unpack(">I", r[d:d + 4])[0] & 0x7FFFFFFF) % 1000000).zfill(6)


def codigo_2fa(aviso=None):
    """Código del administrador de pruebas. SIBIO no acepta dos veces el mismo código (anti-repetición),
    así que si el código de estos 30 s ya se usó, espera al siguiente.
    `aviso(segundos)` se llama cada segundo de espera, para mostrar la cuenta regresiva.
    Devuelve el código; los segundos esperados quedan en codigo_2fa.espera."""
    secreto = os.environ.get("SIBIO_ADMIN_TOTP", "").strip()
    if not secreto:
        raise FalloInfraestructura("El administrador de pruebas tiene 2FA y falta SIBIO_ADMIN_TOTP en .env")
    try:
        with open(_ARCHIVO_PASO, encoding="utf-8") as fh:
            usado = int(fh.read().strip() or 0)
    except (OSError, ValueError):
        usado = 0
    paso = int(time.time() // 30)
    codigo_2fa.espera = 0
    if paso <= usado:
        fin = (usado + 1) * 30 + 0.5
        codigo_2fa.espera = max(0, round(fin - time.time()))
        while (falta := fin - time.time()) > 0:
            if aviso:
                try:
                    aviso(max(1, round(falta)))
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(min(1, falta))
        paso = int(time.time() // 30)
    os.makedirs(os.path.dirname(_ARCHIVO_PASO), exist_ok=True)
    with open(_ARCHIVO_PASO, "w", encoding="utf-8") as fh:
        fh.write(str(paso))
    return totp(secreto, paso)


codigo_2fa.espera = 0
MOTIVO_ESPERA_2FA = "SIBIO no acepta dos veces el mismo código (protección anti-repetición)"


def aviso_2fa(registro):
    """Función para codigo_2fa(aviso=...): publica 'Esperando un código nuevo: N s' en el paso en curso."""
    if registro is None:
        return None
    return lambda s: registro.avisar(f"Esperando un código 2FA nuevo: {s} s. {MOTIVO_ESPERA_2FA}")


def nota_espera_2fa():
    return f" (se esperó {codigo_2fa.espera} s a un código nuevo: {MOTIVO_ESPERA_2FA})" if codigo_2fa.espera else ""
