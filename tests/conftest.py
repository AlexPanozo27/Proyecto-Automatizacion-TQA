"""
Plugin de pytest del proyecto:
  --suite smoke|sanity|...     ejecuta una suite
  --casos TC-API-01,TC-E2E-02  ejecuta casos sueltos
  --salida carpeta             donde se guarda resultados.jsonl y las capturas
  --catalogo archivo.json      solo lista los casos (lo usa la web)
Cada caso termina en PASS, FAIL (fallo funcional), ERROR (infraestructura) o SKIPPED.
"""
import json
import os
import re
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(__file__))
try:   # también al correr pytest por consola
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass
from soporte import API, FalloInfraestructura, Registro, aviso_2fa, codigo_2fa, nota_espera_2fa  # noqa: E402

SIBIO_URL = os.environ.get("SIBIO_URL", "http://127.0.0.1:5000")
ADMIN = (os.environ.get("SIBIO_ADMIN", "admin"), os.environ.get("SIBIO_ADMIN_CLAVE", ""))
OPERADOR = (os.environ.get("SIBIO_OPERADOR", "jperez"), os.environ.get("SIBIO_OPERADOR_CLAVE", ""))
SUPERVISOR = (os.environ.get("SIBIO_SUPERVISOR", "agutierrez"), os.environ.get("SIBIO_SUPERVISOR_CLAVE", ""))


def pytest_addoption(parser):
    parser.addoption("--suite", default="")
    parser.addoption("--casos", default="")
    parser.addoption("--salida", default="reportes/ultima")
    parser.addoption("--catalogo", default="")


def _ficha(item):
    return getattr(getattr(item, "function", None), "_caso", None)


def pytest_collection_modifyitems(config, items):
    suite = config.getoption("--suite").strip().lower()
    casos = {c.strip() for c in config.getoption("--casos").split(",") if c.strip()}
    elegidos, fuera = [], []
    for it in items:
        f = _ficha(it)
        ok = f is not None and (not suite or suite in f["suites"]) and (not casos or f["id"] in casos)
        (elegidos if ok else fuera).append(it)
    items[:] = elegidos
    if fuera:
        config.hook.pytest_deselected(items=fuera)
    destino = config.getoption("--catalogo")
    if destino:
        with open(destino, "w", encoding="utf-8") as fh:
            json.dump([_ficha(i) for i in elegidos], fh, ensure_ascii=False, indent=1)


def pytest_collection_finish(session):
    if session.config.getoption("--catalogo"):
        session.items.clear()


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def api():
    return API(SIBIO_URL)


@pytest.fixture(scope="session")
def sibio(api):
    """Precondición de infraestructura: SIBIO-RFID encendido y respondiendo."""
    r = api.llamar("GET", "/api/auth/opciones")
    if r.status_code >= 500:
        raise FalloInfraestructura(f"SIBIO-RFID respondió HTTP {r.status_code}")
    return api


_SESION_ADMIN = {}


def login_admin(api, registro=None):
    """Inicio de sesión completo del administrador: contraseña y, si lo pide, código 2FA.
    Con `registro` deja cada etapa como un paso del caso."""
    from contextlib import nullcontext
    paso = registro.paso if registro else (lambda _t: nullcontext({}))
    with paso("Enviar usuario y contraseña del administrador (POST /api/auth/login)") as p:
        r = api.llamar("POST", "/api/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
        p["observado"] = f"HTTP {r.status_code}; " + ("pide código 2FA" if r.datos.get("requiere_2fa") else
                                                      f"rol={r.datos.get('usuario', {}).get('rol')}")
        if r.status_code != 200:
            raise FalloInfraestructura(f"El administrador de pruebas no pudo entrar (HTTP {r.status_code}: {r.datos.get('error')})")
    if r.datos.get("requiere_2fa"):
        with paso("Enviar el código de 6 dígitos del autenticador (POST /api/auth/2fa/verificar)") as p:
            r = api.llamar("POST", "/api/auth/2fa/verificar", json={"desafio": r.datos["desafio"], "codigo": codigo_2fa(aviso_2fa(registro))})
            p["observado"] = f"HTTP {r.status_code}; {r.datos.get('error') or 'código aceptado'}" + nota_espera_2fa()
            assert r.status_code == 200, f"SIBIO rechazó el código 2FA: {r.datos.get('error')}"
    if r.datos.get("usuario", {}).get("debe_vincular_2fa"):
        raise FalloInfraestructura("El administrador de pruebas debe vincular su app autenticadora (2FA) en SIBIO: "
                                   "vincúlelo y ponga su secreto en SIBIO_ADMIN_TOTP")
    _SESION_ADMIN["token"] = r.datos["token"]
    return r.datos


@pytest.fixture(scope="session")
def token_admin(sibio):
    if "token" not in _SESION_ADMIN:
        login_admin(sibio)
    return _SESION_ADMIN["token"]


@pytest.fixture
def registro(request):
    salida = request.config.getoption("--salida")
    f = _ficha(request.node) or {"id": request.node.name}
    r = Registro(os.path.join(salida, "capturas", f["id"]), f["id"])
    request.node._registro = r
    return r


@pytest.fixture(scope="session")
def navegador():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    ver = os.environ.get("QA_VER_NAVEGADOR", "0") == "1"
    opciones = {"headless": not ver}
    if ver:   # navegador visible: un poco más lento para que se vea cada clic (como Selenium en vivo)
        opciones["slow_mo"] = int(os.environ.get("QA_LENTO_MS", "250"))
    ruta = os.environ.get("CHROMIUM_PATH")
    if ruta:
        opciones["executable_path"] = ruta
    try:
        b = pw.chromium.launch(**opciones)
    except Exception as e:  # noqa: BLE001
        pw.stop()
        raise FalloInfraestructura(f"No se pudo abrir el navegador: {e}") from e
    yield b
    b.close()
    pw.stop()


# ---------- modo presentación (para la defensa): rótulo del paso y resaltado del elemento antes de usarlo ----------
PRESENTACION = os.environ.get("QA_PRESENTACION", "0") == "1" and os.environ.get("QA_VER_NAVEGADOR", "0") == "1"
_JS_PRESENTACION = """(() => {
  if (window.__qa) return;
  const qa = window.__qa = {oculto: false};
  qa.montar = () => {
    const raiz = document.documentElement; if (!raiz) return;
    if (!document.getElementById('qa-estilo')) {
      const st = document.createElement('style'); st.id = 'qa-estilo';
      st.textContent = `#qa-rotulo{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:2147483647;
        max-width:86vw;padding:10px 18px;border-radius:999px;background:rgba(15,23,32,.94);color:#fff;
        font:600 15px/1.35 system-ui,Segoe UI,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.45);
        border:1.5px solid #ffb020;pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        #qa-rotulo::before{content:'PRUEBA AUTOMÁTICA  ';color:#ffb020;font-weight:800;letter-spacing:.04em}
        #qa-rotulo::after{content:attr(data-t)}
        [data-qa-resaltado]{outline:3px solid #ffb020 !important;outline-offset:3px !important;
        box-shadow:0 0 0 7px rgba(255,176,32,.32) !important;transition:box-shadow .15s}`;
      raiz.appendChild(st);
    }
    let r = document.getElementById('qa-rotulo');
    if (!r) { r = document.createElement('div'); r.id = 'qa-rotulo'; r.setAttribute('aria-hidden', 'true'); raiz.appendChild(r); }
    const t = window.__qaTexto || '';
    r.setAttribute('data-t', t); r.style.display = t && !qa.oculto ? 'block' : 'none';
  };
  qa.ocultar = (si) => { qa.oculto = si;
    if (si) document.querySelectorAll('[data-qa-resaltado]').forEach((e) => e.removeAttribute('data-qa-resaltado'));
    qa.montar(); };
  qa.resaltar = (el) => { qa.montar(); el.setAttribute('data-qa-resaltado', '1');
    setTimeout(() => el.removeAttribute('data-qa-resaltado'), 1300); };
  document.addEventListener('DOMContentLoaded', qa.montar); qa.montar();
})();"""


def _activar_resaltado():
    """Antes de cada clic o escritura, marca el elemento con un borde naranja. No cambia lo que la prueba hace:
    si el resaltado falla (elemento aún no visible), se ignora y la acción real corre igual, con sus esperas."""
    from playwright.sync_api import Locator, Page
    if getattr(Locator, "_qa_resaltado", False):
        return
    Locator._qa_resaltado = True

    def marcar(loc):
        try:
            loc.first.evaluate("el => window.__qa && window.__qa.resaltar(el)", timeout=2500)
        except Exception:  # noqa: BLE001
            pass

    def envolver(clase, nombre, por_selector):
        original = getattr(clase, nombre)

        def accion(self, *a, **kw):
            marcar(self.locator(a[0]) if por_selector and a else self)
            return original(self, *a, **kw)
        accion.__name__ = nombre
        setattr(clase, nombre, accion)

    for nombre in ("click", "fill", "check", "uncheck", "press", "select_option", "dblclick"):
        envolver(Locator, nombre, False)
        envolver(Page, nombre, True)


@pytest.fixture
def pagina(navegador, sibio, registro):
    ctx = navegador.new_context(viewport={"width": 1366, "height": 800}, locale="es-BO")
    if PRESENTACION:
        ctx.add_init_script(_JS_PRESENTACION)
        _activar_resaltado()
        registro.presentacion = True
    p = ctx.new_page()
    p.set_default_timeout(10000)
    registro.page = p
    yield p
    ctx.close()


# ---------- resultados ----------
def _clasificar(rep, call):
    if rep.skipped:
        motivo = rep.longrepr[2] if isinstance(rep.longrepr, tuple) else str(rep.longrepr)
        return "SKIPPED", motivo.replace("Skipped: ", "")
    if rep.passed:
        return "PASS", ""
    exc = call.excinfo.value if call.excinfo else None
    texto = str(exc).strip().split("\n")[0][:400] if exc else ""
    if isinstance(exc, AssertionError):
        return "FAIL", "Fallo funcional: " + (texto or "la verificación no se cumplió")
    nombre = type(exc).__name__ if exc else "Error"
    m = re.search(r"waiting for (.+)", str(exc or ""))
    if nombre == "TimeoutError" and m:
        return "ERROR", (f"Error del script: el elemento {m.group(1).strip()[:160]} no apareció en el panel "
                         "(¿cambió la interfaz?). Se puede reparar con IA.")
    if isinstance(exc, FalloInfraestructura) or nombre in ("ConnectionError", "Timeout", "TimeoutError", "Error"):
        return "ERROR", "Error de infraestructura: " + (texto or nombre)
    return "ERROR", f"Error del script ({nombre}): {texto}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    f = _ficha(item)
    if f is None:
        return
    fin_caso = (rep.when == "call") or (rep.when == "setup" and (rep.failed or rep.skipped))
    if not fin_caso:
        return
    estado, obs = _clasificar(rep, call)
    reg = getattr(item, "_registro", None)
    pasos = reg.pasos if reg else []
    fallido = next((p for p in pasos if p["estado"] != "PASS"), None)
    if estado == "PASS" and not obs:
        obs = f"{len(pasos)} pasos verificados"
    fila = {**f, "estado": estado, "observacion": obs, "pasos": pasos,
            "paso_fallido": fallido["n"] if fallido else None,
            "duracion_s": round(rep.duration if rep.when == "call" else 0, 2),
            "fin": time.strftime("%Y-%m-%d %H:%M:%S")}
    salida = item.config.getoption("--salida")
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "resultados.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Avisa a la web qué caso está corriendo ahora."""
    f = _ficha(item)
    if f:
        salida = item.config.getoption("--salida")
        os.makedirs(salida, exist_ok=True)
        with open(os.path.join(salida, "actual.txt"), "w", encoding="utf-8") as fh:
            fh.write(f["id"])
