"""Jarvis: asistente conversacional del QA Lab. Responde con el conocimiento del proyecto y los datos reales
(catálogo, historial y la ejecución que se le pase). No ve el .env ni ninguna clave."""
import os
import re
import unicodedata

from motor import ejecutor, ia

RAIZ = ejecutor.RAIZ
_conocimiento = None

SISTEMA = """Eres Jarvis, el asistente del QA Lab de Alexander (plataforma de automatización de pruebas de SIBIO-RFID).
Hablas en español de Bolivia, claro, cálido y con algo de personalidad (como el Jarvis de Iron Man, pero sin exagerar).
Tu público puede no saber nada de QA: explica con palabras simples y con ejemplos de SUS casos reales (cita IDs como
TC-API-01). Reglas:
1. Usa SOLO la información de CONOCIMIENTO y DATOS de abajo. Si algo no está ahí, dilo ("eso no lo tengo registrado").
   Nunca inventes resultados, números, casos ni funciones.
2. Nunca muestres ni pidas claves, contraseñas, tokens ni el contenido del .env.
3. Sé breve: 2 a 6 oraciones o una lista corta, salvo que te pidan detalle. Puedes usar **negritas** y viñetas con "- ".
4. Si te piden consejos o ideas a futuro, dalos como sugerencias concretas y di cuáles ya existen y cuáles no.
5. Si te piden explicar una ejecución: qué se probó, qué significa cada resultado (PASS/FAIL/ERROR/SKIPPED) y por qué
   importa, en lenguaje para alguien que no es técnico.
6. Tú NO ejecutas pruebas desde esta respuesta: si te piden correr una suite, di que escriban por ejemplo
   "corre el Smoke" o "ejecuta la suite de Seguridad" y que tú pedirás confirmación antes de lanzarla.
Responde SOLO un JSON: {"respuesta": "texto", "sugerencias": ["pregunta corta 1", "pregunta corta 2", "pregunta corta 3"]}
Las sugerencias son preguntas que el usuario podría hacerte a continuación (máx. 60 caracteres cada una)."""


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _sin_codigo(texto, limite=14000):
    return re.sub(r"```.*?```", "", texto, flags=re.S)[:limite]


def conocimiento():
    """Lo que Jarvis sabe siempre: su base, el README del QA Lab, las mejoras propuestas y la documentación de
    SIBIO (README y análisis por módulo, leídos de SIBIO_DOCS_DIR; por defecto la carpeta de arriba)."""
    global _conocimiento
    if _conocimiento is None:
        partes = [_leer(os.path.join(RAIZ, "docs", "conocimiento_jarvis.md")),
                  "# README del QA Lab\n" + _sin_codigo(_leer(os.path.join(RAIZ, "README.md"))),
                  _leer(os.path.join(RAIZ, "docs", "mejoras_sibio.md"))]
        base = os.environ.get("SIBIO_DOCS_DIR") or os.path.dirname(RAIZ)
        for titulo, ruta in (("README de SIBIO-RFID", "README.md"),
                             ("Análisis de SIBIO por módulo", os.path.join("documentacion", "ANALISIS_DEL_SISTEMA_POR_MODULO.md"))):
            texto = _leer(os.path.join(base, ruta))
            if texto:
                partes.append(f"# {titulo} (documento de Alexander)\n" + _sin_codigo(texto))
        _conocimiento = "\n\n".join(p for p in partes if p)
    return _conocimiento


_api = None
_PREGUNTA_API = r"\bapi|endpoint|lector|autentic|cabecera|token|\bruta|swagger|openapi|documentacion de la api|/api/|\b(get|post|put|patch|delete)\b"


def api_sibio():
    """Lista compacta de la API de SIBIO: en vivo desde su OpenAPI (así conoce rutas nuevas) o, si SIBIO está
    apagado, la copia guardada en docs/sibio_api.md."""
    global _api
    if _api is None:
        try:
            import requests
            d = requests.get(os.environ.get("SIBIO_URL", "http://127.0.0.1:5000") + "/api/docs/openapi.json", timeout=4).json()
            grupos = {}
            for ruta, ops in d["paths"].items():
                for metodo, op in ops.items():
                    if metodo in ("get", "post", "put", "patch", "delete"):
                        q = re.search(r"\*\*Qui[eé]n puede usarla:\*\*\s*([^\n]+)", op.get("description", ""))
                        quien = q.group(1).split(":")[0].strip().rstrip(".") if q else ""
                        grupos.setdefault((op.get("tags") or ["Otros"])[0], []).append(
                            f"- {metodo.upper()} {ruta} — {op.get('summary', '').strip()}" + (f" ({quien})" if quien else ""))
            n = sum(len(v) for v in grupos.values())
            _api = (f"# API de SIBIO-RFID (en vivo desde /api/docs/openapi.json): {n} operaciones en {len(grupos)} grupos. "
                    "REST + JSON, sesión con token JWT (los lectores RFID usan X-API-Key); documentación Swagger en /api/docs.\n"
                    + "\n".join(f"## {g} ({len(v)})\n" + "\n".join(v) for g, v in grupos.items()))
        except Exception:  # noqa: BLE001 - SIBIO apagado: copia guardada
            _api = _leer(os.path.join(RAIZ, "docs", "sibio_api.md"))
    return _api


def _datos(eid=None):
    cat = ejecutor.catalogo()
    casos = [f"{c['id']} · {c['nombre']} · suites {','.join(c['suites'])} · {c['tipo']} · {c.get('modulo', '')}" for c in cat]
    hist = ejecutor.historial(15)
    filas = [f"{h['id']} · {h['etiqueta']} · {h['estado']} · {h['inicio']} · {h['duracion_s']} s · "
             f"PASS {h['resumen']['PASS']} FAIL {h['resumen']['FAIL']} ERROR {h['resumen']['ERROR']} SKIPPED {h['resumen']['SKIPPED']}"
             + (f" · no pasaron: {', '.join(f['id'] for f in h['fallidos'])}" if h["fallidos"] else "") for h in hist]
    todas = [h for h in ejecutor.historial(40) if h.get("resumen")]
    ejecutados = sum(h["resumen"]["PASS"] + h["resumen"]["FAIL"] + h["resumen"]["ERROR"] for h in todas)
    aprobados = sum(h["resumen"]["PASS"] for h in todas)
    duraciones = [h["duracion_s"] for h in todas if h.get("duracion_s")]
    metricas = (f"MÉTRICAS DEL HISTORIAL ({len(todas)} ejecuciones): tasa de éxito global "
                f"{round(100 * aprobados / ejecutados) if ejecutados else 0} % ({aprobados} PASS de {ejecutados} ejecutados); "
                f"FAIL {sum(h['resumen']['FAIL'] for h in todas)}, ERROR {sum(h['resumen']['ERROR'] for h in todas)}; "
                f"duración media {round(sum(duraciones) / len(duraciones), 1) if duraciones else 0} s.\n\n")
    texto = metricas + (f"CATÁLOGO ({len(cat)} casos):\n" + "\n".join(casos) + "\n\nÚLTIMAS EJECUCIONES (más reciente primero):\n"
             + ("\n".join(filas) or "Ninguna todavía."))
    e = eid and ejecutor.obtener(eid)
    if e:
        det = []
        for c in e["casos"]:
            det.append(f"- {c['id']} {c['nombre']} → {c['estado']}: {c['observacion']}")
            det += [f"    paso {p['n']}: {p['accion']} → {p['estado']}: {p.get('observado', '')[:180]}" for p in c.get("pasos", [])][:8]
        texto += (f"\n\nEJECUCIÓN SELECCIONADA {e['id']} ({e['etiqueta']}, {e.get('tipo')}, estado {e['estado']}, "
                  f"duración {e.get('duracion_s')} s):\n" + "\n".join(det))
        if e.get("resumen_ia"):
            texto += "\nAnálisis de fallos ya generado: " + e["resumen_ia"][:800]
    return texto


# Selector del chat: "auto" usa los modelos del .env; los otros dos fijan principal y respaldo.
MODOS = {"rapido": ("gemini-flash-lite-latest", "gemini-3-flash-preview"),
         "potente": ("gemini-3-flash-preview", "gemini-flash-lite-latest")}

# "Jarvis, corre el Smoke": se detecta aquí, sin IA (instantáneo y sin gastar tokens). La web pide confirmación.
_VERBO = r"(corre|correr|corras|ejecuta|ejecutar|ejecutes|lanza|lanzar|lances|inicia|iniciar|arranca|arrancar|run|correme|ejecutame|lanzame)"
_ALIAS = [("autocuracion", r"autocura|auto-cura|autorepar"), ("seguridad", r"seguridad|security"),
          ("regression", r"regresion|regression"), ("integration", r"integracion|integration"),
          ("e2e", r"\be2e\b|end to end|extremo a extremo|punta a punta"), ("retest", r"retest|re-test"),
          ("smoke", r"smoke|humo"), ("sanity", r"sanity|cordura"), ("performance", r"rendimiento|performance"),
          ("estres", r"estres|stress"), ("soak", r"\bsoak\b|resistencia"), ("ia", r"generadas por ia|casos de la ia|suite ia\b|suite de ia")]


def _plano(t):
    return unicodedata.normalize("NFD", t.lower()).encode("ascii", "ignore").decode()


def detectar_orden(mensaje):
    """Devuelve {tipo, suite, nombre, casos} si el mensaje pide correr una suite; si es una pregunta (\"¿cómo se
    ejecuta…?\") o no nombra una suite conocida, devuelve None."""
    t = _plano(mensaje)
    if not re.search(rf"\b{_VERBO}\b", t):
        return None
    if re.search(rf"\b(como|que|cual|cuando|cuanto|donde|porque|por que|para que)\b\s+(se\s+|le\s+|lo\s+)?(\w+\s+)?{_VERBO}\b", t):
        return None
    for suite, patron in _ALIAS:
        if re.search(patron, t):
            tipo = next(k for k, lista in ejecutor.SUITES.items() if suite in dict(lista))
            n = sum(1 for c in ejecutor.catalogo() if suite in c["suites"])
            return {"tipo": tipo, "suite": suite, "nombre": ejecutor.NOMBRE_SUITE[suite], "casos": n} if n else None
    return None


def _respuesta_orden(o):
    extra = {"seguridad": " Recuerda: la suite de Seguridad se corre una sola vez seguida.",
             "e2e": " Abrirá Edge y lo verás trabajar en vivo.",
             "autocuracion": " Si falla por el localizador viejo, puedo repararlo con IA."}.get(o["suite"], "")
    return {"respuesta": f"Entendido. Preparé la suite **{o['nombre']}** ({o['casos']} caso{'' if o['casos'] == 1 else 's'}, "
                         f"{'funcional' if o['tipo'] == 'funcional' else 'no funcional'}). ¿La lanzo? El informe irá al correo "
                         f"del paso 3.{extra}",
            "sugerencias": [], "accion": {"ejecutar": o}, "_ia": {"modelo": "orden directa", "segundos": 0}}


ULTIMA = {}   # modelo que respondió de verdad la última vez (puede ser el de respaldo)
_PREGUNTA_MODELO = r"\b(que|cual|con que)\s+(modelo|ia|inteligencia artificial|llm)\b|\bmodelo (eres|usas|estas usando|de ia)\b|\bque ia eres\b"


def _respuesta_modelo(modo):
    usa = (MODOS.get(modo) or (None,))[0] or os.environ.get("GEMINI_MODELO", "gemini-3-flash-preview")
    resp = (MODOS.get(modo) or (None, None))[1] or os.environ.get("GEMINI_MODELO_RESPALDO", "gemini-flash-lite-latest")
    etiqueta = {"rapido": "⚡ Rápido", "potente": "🧠 Potente"}.get(modo, "🔄 Auto")
    t = (f"Funciono con **Gemini de Google**. Ahora estoy en modo **{etiqueta}**: mi modelo principal es **{usa}** y, "
         f"si Google lo tiene saturado, respondo con **{resp}**.")
    if ULTIMA.get("modelo"):
        t += (f" Mi última respuesta la dio **{ULTIMA['modelo']}**"
              + (f" en {str(ULTIMA['segundos']).replace('.', ',')} s" if ULTIMA.get("segundos") is not None else "")
              + (" (el principal estaba saturado y entró el de respaldo)." if ULTIMA.get("respaldo") else "."))
    t += " Puedes cambiarme con el selector de arriba: Rápido responde en pocos segundos y Potente razona más pero tarda más."
    return {"respuesta": t, "sugerencias": ["¿Qué diferencia hay entre los modelos?", "Corre el Smoke"],
            "_ia": {"modelo": "orden directa", "segundos": 0}}


def responder(mensaje, historial=None, eid=None, modo="auto", nombre=""):
    mensaje = (mensaje or "").strip()[:1500]
    if not mensaje:
        raise ia.ErrorIA("Escribe una pregunta")
    orden = detectar_orden(mensaje)
    if orden:
        return _respuesta_orden(orden)
    if ia.proveedor() == "gemini" and re.search(_PREGUNTA_MODELO, _plano(mensaje)):
        return _respuesta_modelo(modo)
    if ia.proveedor() in (None, "simulado"):
        return _simulado(mensaje, eid)
    charla = "\n".join(f"{'Usuario' if t.get('rol') == 'usuario' else 'Jarvis'}: {str(t.get('texto', ''))[:600]}"
                       for t in (historial or [])[-8:])
    extra_api = f"\n\nAPI DE SIBIO:\n{api_sibio()}" if re.search(_PREGUNTA_API, _plano(mensaje)) else ""
    pedido = (f"CONOCIMIENTO:\n{conocimiento()}{extra_api}\n\nDATOS:\n{_datos(eid)}\n\nCONVERSACIÓN PREVIA:\n{charla or '(ninguna)'}"
              f"\n\nPREGUNTA ACTUAL: {mensaje}")
    principal, respaldo = MODOS.get(modo, (None, None)) if ia.proveedor() == "gemini" else (None, None)
    nombre = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ ]", "", nombre or "")[:30].strip()
    if nombre:
        pedido += f"\nEl usuario se llama {nombre}: llámalo por su nombre de vez en cuando."
    r = ia._llamar(SISTEMA, pedido, rapido=modo != "potente", modelo=principal, respaldo=respaldo)
    ULTIMA.clear(); ULTIMA.update(ia.ULTIMO)
    sug = [str(s)[:70] for s in (r.get("sugerencias") or []) if s][:3]
    return {"respuesta": str(r.get("respuesta") or "No tengo una respuesta para eso."), "sugerencias": sug,
            "_ia": dict(ia.ULTIMO)}


def _simulado(mensaje, eid):
    """Sin clave de IA: busca el párrafo del conocimiento que más palabras comparte con la pregunta."""
    def claves(t):
        t = unicodedata.normalize("NFD", t.lower()).encode("ascii", "ignore").decode()
        return {w[:6] for w in re.findall(r"\w{4,}", t)}
    palabras = claves(mensaje)
    mejores = sorted((ln for ln in conocimiento().splitlines() if ln.strip().startswith("- ")),
                     key=lambda ln: -len(palabras & claves(ln)))[:3]
    extra = ""
    e = eid and ejecutor.obtener(eid)
    if e:
        r = ejecutor.resumen(e)
        extra = f"\n\nEn la ejecución {e['id']} ({e['etiqueta']}): {r['PASS']} PASS, {r['FAIL']} FAIL, {r['ERROR']} ERROR, {r['SKIPPED']} SKIPPED."
    return {"respuesta": "(Modo simulado, sin clave de IA) Esto encontré en el conocimiento del proyecto:\n"
                         + "\n".join(mejores) + extra,
            "sugerencias": ["¿Qué es una prueba de regresión?", "¿Cómo se envía el correo?", "¿Qué hace la autocuración?"],
            "_ia": {"modelo": "simulado"}}
