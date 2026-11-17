"""Orquestador: lanza pytest en segundo plano, sigue el avance y arma el resultado de cada ejecución."""
import json
import os
import random
import string
import subprocess
import sys
import threading
import time
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTES = os.path.join(RAIZ, "reportes")

SUITES = {
    "funcional": [("smoke", "Smoke"), ("sanity", "Sanity"), ("regression", "Regresión"),
                  ("integration", "Integración"), ("e2e", "E2E"), ("retest", "Retesting de defectos"), ("ia", "Generadas por IA"), ("autocuracion", "Autocuración (demo IA)")],
    "no_funcional": [("performance", "Rendimiento"), ("estres", "Estrés"), ("soak", "Soak (resistencia)"), ("seguridad", "Seguridad")],
}
NOMBRE_SUITE = {k: v for lista in SUITES.values() for k, v in lista}

_ejecuciones = {}
_candado = threading.Lock()
_catalogo = None


def catalogo(refrescar=False):
    """Lista de casos leída de las pruebas reales (pytest --collect-only)."""
    global _catalogo
    if _catalogo is None or refrescar:
        destino = os.path.join(REPORTES, "catalogo.json")
        os.makedirs(REPORTES, exist_ok=True)
        subprocess.run([sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "--catalogo", destino],
                       cwd=RAIZ, capture_output=True, timeout=120)
        with open(destino, encoding="utf-8") as fh:
            _catalogo = json.load(fh)
    return _catalogo


def _nuevo_id():
    return "EJ-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + "".join(random.choices(string.ascii_uppercase, k=2))


VELOCIDADES = ("normal", "presentacion")


def navegador_visible():
    return os.environ.get("QA_VER_NAVEGADOR", "0") == "1"


def crear(tipo, suite, casos, correo, velocidad="normal"):
    cat = catalogo()
    if casos:
        elegidos = [c for c in cat if c["id"] in casos]
        etiqueta = "Casos seleccionados"
    else:
        elegidos = [c for c in cat if suite in c["suites"]]
        etiqueta = NOMBRE_SUITE.get(suite, suite)
    if not elegidos:
        raise ValueError("No hay casos para ejecutar con esa selección")
    eid = _nuevo_id()
    e = {"id": eid, "tipo": tipo, "suite": suite, "etiqueta": etiqueta, "correo": correo,
         "velocidad": velocidad if velocidad in VELOCIDADES else "normal",
         "estado": "pendiente", "creada": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "inicio": None, "fin": None, "duracion_s": None, "actual": None,
         "casos": [{**c, "estado": "NOT RUN", "observacion": "Aún no se ejecuta", "pasos": []} for c in elegidos],
         "informe": {}, "correo_estado": "pendiente", "correo_detalle": "", "salida": os.path.join(REPORTES, eid)}
    with _candado:
        _ejecuciones[eid] = e
    threading.Thread(target=_correr, args=(e,), daemon=True).start()
    return e


def _guardar(e):
    os.makedirs(e["salida"], exist_ok=True)
    with open(os.path.join(e["salida"], "ejecucion.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in e.items() if k != "_proc"}, fh, ensure_ascii=False, indent=1)


def _leer_resultados(e):
    ruta = os.path.join(e["salida"], "resultados.jsonl")
    por_id = {}
    if os.path.exists(ruta):      # aún no existe mientras corre el primer caso: igual se muestran sus pasos en vivo
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                if linea.strip():
                    d = json.loads(linea)
                    por_id[d["id"]] = d
    for i, c in enumerate(e["casos"]):
        if c["id"] in por_id:
            e["casos"][i] = por_id[c["id"]]
    act = os.path.join(e["salida"], "actual.txt")
    if os.path.exists(act):
        with open(act, encoding="utf-8") as fh:
            actual = fh.read().strip()
        e["actual"] = actual
        vivo = {}
        try:
            with open(os.path.join(e["salida"], "vivo.json"), encoding="utf-8") as fh:
                vivo = json.load(fh)
        except (OSError, ValueError):
            pass
        for c in e["casos"]:
            if c["id"] == actual and c["estado"] in ("NOT RUN", "EN CURSO"):
                c["estado"] = "EN CURSO"
                c["observacion"] = "Ejecutándose…"
                if vivo.get("id") == actual:
                    c["pasos"] = vivo.get("pasos", [])


def _correr(e):
    from motor import correo, informes
    e["estado"] = "en_curso"
    e["inicio"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()
    _guardar(e)
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "--salida", e["salida"],
           "--casos", ",".join(c["id"] for c in e["casos"])]
    entorno = os.environ.copy()
    if e.get("velocidad") == "presentacion":      # navegador más lento, con rótulo del paso y resaltado de cada clic
        entorno["QA_PRESENTACION"] = "1"
        entorno["QA_LENTO_MS"] = os.environ.get("QA_PRESENTACION_MS", "450")
    else:
        entorno["QA_PRESENTACION"] = "0"
    try:
        with open(os.path.join(e["salida"], "pytest.log"), "w", encoding="utf-8") as log:
            proc = subprocess.Popen(cmd, cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT, env=entorno)
            e["_proc"] = proc
            while proc.poll() is None:
                _leer_resultados(e)
                time.sleep(0.5)
        _leer_resultados(e)
        codigo = proc.returncode
    except Exception as ex:  # noqa: BLE001
        codigo = -1
        e["error"] = str(ex)
    e.pop("_proc", None)
    e["actual"] = None
    for c in e["casos"]:
        if c["estado"] == "EN CURSO":
            c["estado"], c["observacion"] = "NOT RUN", "La ejecución se detuvo antes de terminar este caso"
        elif c["estado"] == "NOT RUN" and c["observacion"] == "Aún no se ejecuta":
            c["observacion"] = "No se ejecutó (ejecución detenida o cancelada)"
    todos_infra = all(c["estado"] == "ERROR" for c in e["casos"])
    if e.get("cancelada"):
        e["estado"] = "cancelada"
    elif codigo in (0, 1) and not todos_infra:
        e["estado"] = "finalizada"
    else:
        e["estado"] = "fallida"
        e.setdefault("error", "Error de infraestructura: no se pudo ejecutar" if todos_infra
                     else f"pytest terminó con código {codigo}")
    e["fin"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e["duracion_s"] = round(time.time() - t0, 1)
    e["resumen"] = resumen(e)
    try:
        from motor import ia
        e["resumen_ia"] = ia.resumir_fallos(e)
    except Exception as ex:  # noqa: BLE001
        e["resumen_ia"] = None
        e["resumen_ia_error"] = f"No se pudo generar el resumen con IA: {ex}"
    try:
        e["informe"] = informes.generar(e)
    except Exception as ex:  # noqa: BLE001
        e["informe"] = {"error": f"No se pudo generar el informe: {ex}"}
    _guardar(e)
    if e["correo"] and e["informe"].get("pdf"):
        e["correo_estado"] = "enviando"
        ok, detalle = correo.enviar(e)
        e["correo_estado"], e["correo_detalle"] = ("enviado" if ok else "error"), detalle
    else:
        e["correo_estado"] = "sin_envio"
    _guardar(e)


def guardar_defecto(eid, cid, reporte):
    """Guarda el reporte de defecto redactado por la IA dentro de la ejecución (y en un .md para adjuntar)."""
    e = obtener(eid)
    e.setdefault("defectos", {})[cid] = reporte
    e["salida"] = os.path.join(REPORTES, e["id"])
    _guardar(e)
    carpeta = os.path.join(e["salida"], "defectos")
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, f"{reporte['id']}.md"), "w", encoding="utf-8") as fh:
        fh.write(reporte["markdown"])
    return reporte


def resumen(e):
    r = {k: 0 for k in ("PASS", "FAIL", "ERROR", "SKIPPED", "NOT RUN")}
    for c in e["casos"]:
        r[c["estado"]] = r.get(c["estado"], 0) + 1
    ejecutados = r["PASS"] + r["FAIL"]
    r["total"] = len(e["casos"])
    r["exito_pct"] = round(r["PASS"] / ejecutados * 100) if ejecutados else 0
    return r


def cancelar(eid):
    e = obtener(eid)
    if e and e.get("_proc"):
        e["cancelada"] = True
        e["_proc"].terminate()
        return True
    return False


def obtener(eid):
    e = _ejecuciones.get(eid)
    if e is None:
        ruta = os.path.join(REPORTES, eid, "ejecucion.json")
        if os.path.exists(ruta) and "/" not in eid and ".." not in eid:
            with open(ruta, encoding="utf-8") as fh:
                e = json.load(fh)
    return e


def publico(e):
    d = {k: v for k, v in e.items() if not k.startswith("_") and k != "salida"}
    d["resumen"] = e.get("resumen") or resumen(e)
    return d


def historial(limite=40):
    if not os.path.isdir(REPORTES):
        return []
    filas = []
    for nombre in sorted(os.listdir(REPORTES), reverse=True):
        if nombre.startswith("EJ-"):
            e = obtener(nombre)
            if e:
                filas.append({"id": e["id"], "etiqueta": e["etiqueta"], "estado": e["estado"], "inicio": e["inicio"],
                              "tipo": e.get("tipo"), "duracion_s": e["duracion_s"], "resumen": e.get("resumen") or resumen(e),
                              "fallidos": [{"id": c["id"], "nombre": c["nombre"]} for c in e["casos"]
                                           if c["estado"] in ("FAIL", "ERROR")]})
        if len(filas) >= limite:
            break
    return filas
