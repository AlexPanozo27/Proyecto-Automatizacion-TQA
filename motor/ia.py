"""
Asistente de IA para crear pruebas:
  caso en español → ambigüedades y supuestos → Gherkin → locators REALES del panel → código Playwright
  → revisión automática (seguridad + locators) → revisión humana → guardar y ejecutar.
Además resume los fallos de una ejecución para el informe.

Proveedor según IA_PROVEEDOR: gemini (GEMINI_API_KEY), claude (ANTHROPIC_API_KEY) o simulado (sin clave,
respuestas fijas solo para probar la pantalla; se muestra como "simulado").
"""
import ast
import json
import os
import re

import time

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERADOS = os.path.join(RAIZ, "tests", "generados")


def proveedor():
    p = os.environ.get("IA_PROVEEDOR", "").strip().lower()
    if p in ("gemini", "claude", "simulado"):
        return p
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    return None


def estado():
    p = proveedor()
    modelo = {"gemini": os.environ.get("GEMINI_MODELO", "gemini-3-flash-preview"),
              "claude": os.environ.get("CLAUDE_MODELO", "claude-sonnet-5-5"), "simulado": "respuestas fijas"}.get(p)
    return {"proveedor": p, "modelo": modelo}


class ErrorIA(Exception):
    pass


# ---------------------------------------------------------------- llamada al modelo
ULTIMO = {}   # qué modelo respondió la última llamada (para avisar en pantalla si se usó el de respaldo)


def _gemini(modelo, sistema, usuario, espera, pensar=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    cuerpo = {"systemInstruction": {"parts": [{"text": sistema}]},
              "contents": [{"role": "user", "parts": [{"text": usuario}]}],
              "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    if pensar and modelo.startswith("gemini-3"):   # Gemini 3 "piensa" antes de responder; "low" lo acorta mucho
        cuerpo["generationConfig"]["thinkingConfig"] = {"thinkingLevel": pensar}
    cabeceras = {"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")}
    r = requests.post(url, json=cuerpo, timeout=espera, headers=cabeceras)
    if r.status_code == 400 and "thinkingConfig" in cuerpo["generationConfig"]:   # modelo que no acepta el ajuste
        del cuerpo["generationConfig"]["thinkingConfig"]
        r = requests.post(url, json=cuerpo, timeout=espera, headers=cabeceras)
    if r.status_code != 200:
        raise ErrorIA(f"Gemini ({modelo}) respondió HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _llamar(sistema, usuario, rapido=False, modelo=None, respaldo=None):
    """rapido=True (Jarvis): Gemini piensa poco y, si tarda más de JARVIS_ESPERA_S, pasa antes al respaldo.
    modelo/respaldo: los elige Jarvis con su selector (Rápido/Potente); si no, se usan los del .env."""
    p = proveedor()
    ULTIMO.clear()
    inicio = time.monotonic()
    if p == "gemini":
        modelo = modelo or os.environ.get("GEMINI_MODELO", "gemini-3-flash-preview")
        respaldo = (respaldo or os.environ.get("GEMINI_MODELO_RESPALDO", "gemini-flash-lite-latest")).strip()
        espera = int(os.environ.get("JARVIS_ESPERA_S", "15") if rapido else os.environ.get("IA_ESPERA_S", "40"))
        try:   # el modelo principal tiene `espera` segundos; si tarda o está saturado, responde el de respaldo
            texto = _gemini(modelo, sistema, usuario, espera, "low" if rapido else None)
            ULTIMO.update(modelo=modelo, respaldo=False)
        except (requests.Timeout, requests.ConnectionError, ErrorIA) as e:
            saturado = not isinstance(e, ErrorIA) or any(f"HTTP {c}" in str(e) for c in (429, 500, 502, 503, 504))
            if not respaldo or respaldo == modelo or not saturado:
                raise ErrorIA(f"Gemini no respondió: {e}") from e
            texto, ultimo = None, None
            for intento, pausa in enumerate((0, 3, 6)):   # Google a veces responde 503 "high demand" unos segundos
                time.sleep(pausa)
                try:
                    texto = _gemini(respaldo if intento < 2 else modelo, sistema, usuario, 25 if rapido else 90, "low" if rapido else None)
                    break
                except (requests.RequestException, ErrorIA) as e2:
                    ultimo = e2
            if texto is None:
                raise ErrorIA(f"Gemini está saturado y no respondió tras 4 intentos ({ultimo}). Prueba de nuevo en unos segundos.")
            motivo = "tardó demasiado" if isinstance(e, requests.Timeout) else "estaba saturado"
            ULTIMO.update(modelo=respaldo, respaldo=True,
                          aviso=f"{modelo} {motivo}; respondió el modelo de respaldo {respaldo}")
    elif p == "claude":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                          headers={"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01"},
                          json={"model": os.environ.get("CLAUDE_MODELO", "claude-sonnet-5-5"), "max_tokens": 4000,
                                "system": sistema, "messages": [{"role": "user", "content": usuario}]})
        if r.status_code != 200:
            raise ErrorIA(f"Claude respondió HTTP {r.status_code}: {r.text[:200]}")
        texto = "".join(b.get("text", "") for b in r.json()["content"])
    else:
        raise ErrorIA("No hay IA configurada: ponga GEMINI_API_KEY (o ANTHROPIC_API_KEY) en .env")
    ULTIMO["segundos"] = round(time.monotonic() - inicio, 1)
    return _json(texto)


def _json(texto):
    texto = texto.strip()
    m = re.search(r"\{.*\}", texto, re.S)
    try:
        return json.loads(m.group(0) if m else texto)
    except (ValueError, AttributeError) as e:
        raise ErrorIA("La IA no devolvió un JSON válido") from e


# ---------------------------------------------------------------- 1. análisis + Gherkin
SIS_ANALISIS = """Eres un analista QA senior. Recibes un caso de prueba escrito en español por un estudiante para
el panel web de SIBIO-RFID (control penitenciario: reclusos, manillas RFID, alertas, verificación biométrica).
Módulos del menú del panel: {menu}.
Responde SOLO un JSON con estas claves:
 "titulo": nombre corto del caso (máx. 70 caracteres),
 "ambiguedades": lista de objetos {{"duda": qué no está claro, "supuesto": qué supondrás para poder automatizarlo}} (0 a 4),
 "rol": "administrador", "operador" o "supervisor",
 "modulo": módulo principal del menú,
 "objetivo": una oración, "precondiciones": una oración, "datos": datos de prueba,
 "resultado_esperado": una oración verificable,
 "gherkin": escenario en Gherkin en español (Característica / Escenario / Dado / Cuando / Entonces / Y).
No inventes funciones que no estén en el menú. Si el caso pide hardware real (sensor, manilla física), indícalo en ambigüedades."""


def analizar(caso, mapa):
    if proveedor() == "simulado":
        return _simulado_analisis(caso)
    return _llamar(SIS_ANALISIS.format(menu=", ".join(mapa.get("menu", []))), f"Caso de prueba:\n{caso}")


# ---------------------------------------------------------------- 2. código Playwright
SIS_CODIGO = """Eres un ingeniero de automatización. Escribe el CUERPO de una función de prueba Python con Playwright
(API síncrona) para el panel de SIBIO-RFID, a partir del escenario Gherkin.
Variables disponibles: `pagina` (Page de Playwright) y `registro`.
Funciones disponibles (ya importadas, no importes nada):
 - entrar(pagina, registro, rol)          inicia sesión ("administrador", "operador" o "supervisor")
 - ir_a(pagina, registro, "Módulo")       abre un módulo del menú lateral por su nombre exacto
 - expect(...)                            aserciones de Playwright (to_be_visible, to_contain_text, to_have_count...)
 - with registro.paso("Descripción del paso") as p:  agrupa cada paso; dentro pon p["observado"] = "lo que se vio"
REGLAS OBLIGATORIAS:
 1. Usa SOLO locators copiados EXACTAMENTE del MAPA DE LOCATORS REALES de abajo. No inventes ids, nombres ni selectores.
    Excepción: pagina.get_by_text("...") para buscar DATOS visibles (un código, un nombre) que no son controles.
 2. Cada acción y cada verificación va dentro de su propio `with registro.paso(...)` y termina con p["observado"].
 3. Las verificaciones usan expect(...) o assert con mensaje en español.
 4. Nada de imports, archivos, red, os, eval ni exec. Máximo 40 líneas. Sin comentarios largos.
 5. Empieza con entrar(...) y, si hace falta, ir_a(...).
Responde SOLO un JSON: {{"codigo": "<cuerpo de la función, sin la línea def, con 4 espacios de sangría>",
 "locators_usados": ["..."], "nota": "una oración sobre qué verifica"}}

MAPA DE LOCATORS REALES (leído del panel en vivo el {fecha}):
{mapa}"""


def generar_codigo(analisis, mapa):
    from motor.explorador import texto_para_ia
    if proveedor() == "simulado":
        return _simulado_codigo(analisis)
    pedido = (f"Rol: {analisis.get('rol')}\nMódulo: {analisis.get('modulo')}\nDatos: {analisis.get('datos')}\n"
              f"Resultado esperado: {analisis.get('resultado_esperado')}\n\nGherkin:\n{analisis.get('gherkin')}")
    return _llamar(SIS_CODIGO.format(fecha=mapa.get("generado"), mapa=texto_para_ia(mapa)), pedido)


# ---------------------------------------------------------------- 3. revisión automática
PROHIBIDOS = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "getattr", "setattr", "delattr",
              "input", "breakpoint", "vars", "dir", "os", "sys", "subprocess", "requests", "shutil"}
RE_LOC = re.compile(r'pagina\.(?:locator|get_by_role|get_by_label|get_by_placeholder|get_by_text|get_by_test_id)\((?:[^()"]|"[^"]*")*\)')


def _normal(cuerpo):
    lineas = [ln for ln in cuerpo.replace("\t", "    ").splitlines() if ln.strip()]
    if not lineas:
        return ""
    sangria = min(len(ln) - len(ln.lstrip()) for ln in lineas)
    return "\n".join("    " + ln[sangria:] for ln in lineas)


def revisar(cuerpo, mapa):
    """Revisa el código antes de ejecutarlo: sintaxis, instrucciones peligrosas y que los locators existan."""
    from motor.explorador import pantalla_de, todos_los_locators
    cuerpo = _normal(cuerpo)
    problemas, locs = [], []
    fuente = "def prueba(pagina, registro):\n" + cuerpo
    try:
        arbol = ast.parse(fuente)
    except SyntaxError as e:
        return {"ok": False, "codigo": cuerpo, "problemas": [f"Error de sintaxis en la línea {e.lineno - 1}: {e.msg}"], "locators": []}
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            problemas.append("No se permiten imports en el código generado")
        elif isinstance(n, ast.Name) and n.id in PROHIBIDOS:
            problemas.append(f"Uso no permitido: {n.id}")
        elif isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            problemas.append(f"Acceso no permitido a atributo interno: {n.attr}")
        elif isinstance(n, (ast.While, ast.Global, ast.Nonlocal, ast.Lambda)):
            problemas.append(f"Construcción no permitida: {type(n).__name__}")
    if "registro.paso" not in cuerpo:
        problemas.append("El código no registra pasos (registro.paso)")
    if "expect(" not in cuerpo and "assert " not in cuerpo:
        problemas.append("El código no tiene ninguna verificación (expect o assert)")
    reales = todos_los_locators(mapa) if mapa else set()
    donde = pantalla_de(mapa) if mapa else {}
    for loc in dict.fromkeys(RE_LOC.findall(cuerpo)):
        if loc.startswith("pagina.get_by_text("):
            locs.append({"locator": loc, "estado": "dato", "detalle": "Texto de datos (no es un control del panel)"})
        elif loc in reales:
            locs.append({"locator": loc, "estado": "real", "pantalla": donde.get(loc),
                         "detalle": f"Existe en el panel · pantalla «{donde.get(loc)}»"})
        else:
            locs.append({"locator": loc, "estado": "inventado", "detalle": "No está en el mapa del panel"})
            problemas.append(f"Locator que no existe en el panel: {loc}")
    return {"ok": not problemas, "codigo": cuerpo, "problemas": list(dict.fromkeys(problemas)), "locators": locs}


# ---------------------------------------------------------------- 4. guardar como caso
def guardar(analisis, cuerpo, caso_original):
    os.makedirs(GENERADOS, exist_ok=True)
    existentes = [int(m.group(1)) for f in os.listdir(GENERADOS) if (m := re.match(r"test_ia_(\d+)\.py$", f))]
    n = max(existentes, default=0) + 1
    cid = f"TC-IA-{n:02d}"
    rep = lambda k: repr(str(analisis.get(k) or ""))  # noqa: E731
    gherkin = "\n".join("    # " + ln for ln in str(analisis.get("gherkin", "")).splitlines())
    original = "\n".join("    # " + ln for ln in caso_original.strip().splitlines())
    fuente = f'''"""Caso {cid} generado con IA ({estado()['proveedor']}) y revisado antes de ejecutarse."""
from playwright.sync_api import expect  # noqa: F401

from ayudas_e2e import entrar, ir_a  # noqa: F401
from soporte import caso


@caso({cid!r}, {repr("[IA] " + str(analisis.get("titulo", "Caso generado")))}, suites=["e2e", "ia"],
      modulo={rep("modulo")}, objetivo={rep("objetivo")}, precondiciones={rep("precondiciones")},
      datos={rep("datos")}, resultado_esperado={rep("resultado_esperado")})
def test_ia_{n:02d}(pagina, registro):
    # Caso escrito por el usuario:
{original}
    # Gherkin generado:
{gherkin}
{_normal(cuerpo)}
'''
    ast.parse(fuente)
    with open(os.path.join(GENERADOS, f"test_ia_{n:02d}.py"), "w", encoding="utf-8") as fh:
        fh.write(fuente)
    return cid


# ---------------------------------------------------------------- 5. resumen de fallos
SIS_RESUMEN = """Eres un analista QA. Resume en español, para un informe de pruebas, los casos que NO pasaron.
Para cada caso: causa probable en una oración, si es fallo del sistema (FAIL funcional) o del entorno (ERROR de
infraestructura), y qué revisar. Termina con una conclusión de una oración sobre la calidad de la versión.
Si un caso dice "FAIL controlado", explica que es intencional para demostrar el reporte.
Responde SOLO un JSON: {"resumen": "texto en párrafos cortos separados por \\n"}"""


def resumir_fallos(e):
    malos = [c for c in e["casos"] if c["estado"] in ("FAIL", "ERROR")]
    if not malos or not proveedor():
        return None
    if proveedor() == "simulado":
        return ("(Resumen simulado, sin clave de IA) " + " ".join(
            f"{c['id']}: {'fallo funcional' if c['estado'] == 'FAIL' else ('error del script' if c['observacion'].startswith('Error del script') else 'problema de infraestructura')} — {c['observacion']}."
            for c in malos))
    datos = [{"id": c["id"], "nombre": c["nombre"], "estado": c["estado"], "observacion": c["observacion"],
              "paso_fallido": c.get("paso_fallido"),
              "pasos": [f"{p['n']}. {p['accion']} → {p['estado']}: {p['observado']}" for p in c.get("pasos", [])]}
             for c in malos]
    r = e["resumen"]
    return _llamar(SIS_RESUMEN, f"Suite {e['etiqueta']}: {r['PASS']} PASS, {r['FAIL']} FAIL, {r['ERROR']} ERROR, "
                                f"{r['SKIPPED']} SKIPPED.\nCasos que no pasaron:\n"
                                + json.dumps(datos, ensure_ascii=False, indent=1)).get("resumen")


# ---------------------------------------------------------------- 6. autocuración de locators
import difflib  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402

TESTS = os.path.join(RAIZ, "tests")
HISTORIAL_AC = os.path.join(RAIZ, "reportes", "autocuracion")
DEMO = os.path.join(TESTS, "demo", "test_autocuracion.py")
PLANTILLA_DEMO = os.path.join(TESTS, "demo", "plantilla_autocuracion.txt")


class SinReparacion(Exception):
    pass


def _archivo_del_caso(cid):
    for raiz, _, archivos in os.walk(TESTS):
        for f in archivos:
            if f.endswith(".py"):
                ruta = os.path.join(raiz, f)
                with open(ruta, encoding="utf-8") as fh:
                    if re.search(r"@caso\(\s*[\"']" + re.escape(cid) + r"[\"']", fh.read()):
                        return ruta
    return None


def _candidatos(roto, reales, donde, n=10):
    """Locators reales más parecidos al roto (mismo tipo primero). Así a la IA solo le llegan unos pocos."""
    metodo = roto.split("(")[0]
    def nota(loc):
        return difflib.SequenceMatcher(None, roto.lower(), loc.lower()).ratio() + (0.25 if loc.split("(")[0] == metodo else 0)
    return [{"locator": loc, "pantalla": donde.get(loc)} for loc in sorted(reales, key=nota, reverse=True)[:n]]


SIS_REPARAR = """Eres un ingeniero de automatización. Una prueba Playwright del panel de SIBIO-RFID falló porque un locator ya no
existe en el panel (la interfaz cambió). Recibes el paso que falló, el locator roto y una lista de locators que SÍ
existen hoy en el panel. Elige el que cumple la misma función que el roto. NO inventes: el elegido debe ser copiado
EXACTO de la lista. Si ninguno sirve, elige null.
Responde SOLO un JSON: {"elegido": "<locator copiado de la lista o null>", "confianza": "alta" | "media" | "baja",
 "explicacion": "una o dos oraciones en español: qué cambió en el panel y por qué el elegido es el equivalente"}"""


def proponer_reparacion(e, c, mapa):
    """La IA propone el locator nuevo para un caso que falló porque un elemento no apareció."""
    from motor.explorador import pantalla_de, todos_los_locators
    archivo = _archivo_del_caso(c["id"])
    if not archivo:
        raise SinReparacion(f"No encontré el archivo de la prueba {c['id']}")
    with open(archivo, encoding="utf-8") as fh:
        fuente = fh.read()
    reales, donde = todos_los_locators(mapa), pantalla_de(mapa)
    malo = next((p for p in c.get("pasos", []) if p.get("detalle_error")), None)
    en_codigo = [l for l in dict.fromkeys(RE_LOC.findall(fuente)) if not l.startswith("pagina.get_by_text(")]
    roto = None
    if malo:   # el error de Playwright dice qué esperaba: "waiting for get_by_label("Buscar internos")"
        m = re.search(r"waiting for (.+)", malo["detalle_error"])
        esperado = m and m.group(1).strip()
        roto = next((l for l in en_codigo if esperado and esperado.startswith(l[len("pagina."):])), None)
    roto = roto or next((l for l in en_codigo if l not in reales), None)
    if not roto:
        raise SinReparacion("Todos los locators de esta prueba existen en el panel: el fallo no es por un cambio de "
                            "interfaz, así que no se repara con IA (revísalo como defecto o como dato de prueba).")
    if roto in reales:
        raise SinReparacion(f"El locator {roto} sí existe en el panel; el elemento quizá tardó en aparecer. "
                            "Vuelve a ejecutar antes de cambiar la prueba.")
    cand = _candidatos(roto, reales, donde)
    if proveedor() in (None, "simulado"):
        r = {"elegido": cand[0]["locator"], "confianza": "media",
             "explicacion": "Modo simulado (sin IA): se propone el locator real más parecido por texto."}
    else:
        r = _llamar(SIS_REPARAR, json.dumps({
            "paso_que_fallo": malo and malo["accion"], "error": malo and malo["detalle_error"][:500],
            "locator_roto": roto, "locators_que_existen": [f"{x['locator']}  (pantalla {x['pantalla']})" for x in cand]},
            ensure_ascii=False, indent=1))
    elegido = (r.get("elegido") or "").split("  (pantalla")[0].strip()
    if not elegido:
        raise SinReparacion("La IA no encontró un equivalente en el panel actual. " + str(r.get("explicacion") or ""))
    if elegido not in reales:      # la IA no puede inventar: solo vale lo que existe en el panel
        raise SinReparacion(f"La IA propuso {elegido}, que no existe en el panel. Se descarta.")
    linea = next((ln.strip() for ln in fuente.splitlines() if roto in ln), roto)
    return {"caso": c["id"], "archivo": os.path.relpath(archivo, RAIZ).replace(os.sep, "/"), "roto": roto, "nuevo": elegido,
            "pantalla": donde.get(elegido), "confianza": r.get("confianza") or "media",
            "explicacion": r.get("explicacion") or "", "antes": linea, "despues": linea.replace(roto, elegido),
            "candidatos": [x for x in cand if x["locator"] != elegido][:3], "mapa_fecha": mapa.get("generado"),
            "modelo": dict(ULTIMO) or {"modelo": "simulado"}}


def aplicar_reparacion(cid, roto, nuevo, mapa):
    """Cambia el locator en el archivo de la prueba (con copia de respaldo) y deja constancia."""
    from motor.explorador import todos_los_locators
    if nuevo not in todos_los_locators(mapa):
        raise SinReparacion("El locator nuevo no existe en el panel")
    archivo = _archivo_del_caso(cid)
    if not archivo:
        raise SinReparacion(f"No encontré el archivo de la prueba {cid}")
    with open(archivo, encoding="utf-8") as fh:
        fuente = fh.read()
    if roto not in fuente:
        raise SinReparacion("El locator roto ya no está en la prueba (¿ya se reparó?)")
    nueva = fuente.replace(roto, nuevo)
    ast.parse(nueva)
    os.makedirs(HISTORIAL_AC, exist_ok=True)
    marca = time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(archivo, os.path.join(HISTORIAL_AC, f"{os.path.basename(archivo)}.{marca}.bak"))
    with open(archivo, "w", encoding="utf-8") as fh:
        fh.write(nueva)
    with open(os.path.join(HISTORIAL_AC, "historial.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "caso": cid, "archivo": os.path.relpath(archivo, RAIZ),
                             "antes": roto, "despues": nuevo}, ensure_ascii=False) + "\n")
    return {"caso": cid, "veces": nueva.count(nuevo)}


def restaurar_demo():
    shutil.copyfile(PLANTILLA_DEMO, DEMO)
    return True


# ---------------------------------------------------------------- 7. reporte de defecto (bug report)
SEVERIDADES = ("Crítica", "Alta", "Media", "Baja")
SIS_DEFECTO = """Eres un analista QA senior. Un caso de prueba automatizado de SIBIO-RFID (control penitenciario:
reclusos, manillas RFID, alertas, verificación biométrica) terminó en FAIL. Redacta el reporte de defecto en español,
claro y sin adornos, para que un desarrollador pueda reproducirlo. Usa SOLO los datos que recibes: no inventes
pasos, pantallas, códigos HTTP ni valores que no estén en la evidencia.
Responde SOLO un JSON con estas claves:
 "titulo": qué falla y dónde, en una línea (máx. 90 caracteres, sin el id del caso),
 "severidad": "Crítica", "Alta", "Media" o "Baja" (impacto en la operación del penal),
 "prioridad": "Alta", "Media" o "Baja" (urgencia de corregirlo),
 "justificacion": una oración que explique la severidad,
 "pasos_reproducir": lista de 3 a 7 pasos numerables que un humano puede repetir a mano,
 "resultado_obtenido": una o dos oraciones con lo que el sistema hizo realmente (valores exactos de la evidencia),
 "causa_probable": una oración; es una hipótesis, dilo como hipótesis,
 "recomendacion": una oración con qué revisar o corregir,
 "es_defecto_real": true o false. Pon false si el caso dice "FAIL controlado" (falla a propósito para la demostración)
   o si el fallo parece venir de los datos de prueba y no del sistema."""


def reporte_defecto(e, c):
    """Arma el reporte de defecto de un caso en FAIL. Los hechos (ambiente, esperado, evidencia) salen de la
    ejecución real; la IA solo redacta título, severidad, pasos, causa probable y recomendación."""
    from datetime import datetime
    pasos = c.get("pasos", [])
    malo = next((p for p in pasos if p["estado"] != "PASS"), None)
    if proveedor() == "simulado" or not proveedor():
        r = _simulado_defecto(c, malo)
    else:
        datos = {k: c.get(k) for k in ("id", "nombre", "modulo", "objetivo", "precondiciones", "datos",
                                       "resultado_esperado", "observacion")}
        datos["pasos_ejecutados"] = [f"{p['n']}. {p['accion']} → {p['estado']}: {p['observado']}" for p in pasos]
        r = _llamar(SIS_DEFECTO, "Caso en FAIL:\n" + json.dumps(datos, ensure_ascii=False, indent=1))
    sev = str(r.get("severidad", "")).strip().capitalize()
    sev = {"Critica": "Crítica"}.get(sev, sev)
    captura = (malo or {}).get("captura")
    rep = {
        "id": f"DEF-{e['id'][3:11]}-{c['id'].replace('TC-', '')}",
        "caso": c["id"], "ejecucion": e["id"], "fecha": c.get("fin") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "titulo": str(r.get("titulo") or c["nombre"])[:120],
        "severidad": sev if sev in SEVERIDADES else "Media",
        "prioridad": str(r.get("prioridad") or "Media").strip().capitalize(),
        "justificacion": str(r.get("justificacion") or ""),
        "modulo": c.get("modulo") or "",
        "ambiente": f"SIBIO-RFID en {os.environ.get('SIBIO_URL', 'http://127.0.0.1:5000')} · ejecución {e['id']} ({e.get('etiqueta')})",
        "precondiciones": c.get("precondiciones") or "",
        "datos": c.get("datos") or "",
        "pasos_reproducir": [str(x) for x in (r.get("pasos_reproducir") or [p["accion"] for p in pasos])][:8],
        "resultado_esperado": c.get("resultado_esperado") or "",
        "resultado_obtenido": str(r.get("resultado_obtenido") or c.get("observacion") or ""),
        "paso_fallido": malo and f"Paso {malo['n']}: {malo['accion']} → {malo['observado']}",
        "evidencia": ([f"Captura del paso fallido: capturas/{c['id']}/{os.path.basename(captura)}"] if captura else [])
                     + [f"Informe de la ejecución {e['id']} (PDF y HTML)"],
        "captura": captura,
        "causa_probable": str(r.get("causa_probable") or ""),
        "recomendacion": str(r.get("recomendacion") or ""),
        "es_defecto_real": bool(r.get("es_defecto_real", True)),
        "redactado_por": ("una plantilla fija, sin IA (modo simulado)" if proveedor() in (None, "simulado") else
                          f"IA ({estado()['proveedor']} · {estado()['modelo']})")
                         + "; los datos de ambiente, resultado esperado y evidencia salen de la ejecución real",
    }
    rep["markdown"] = _defecto_md(rep)
    return rep


def _defecto_md(d):
    pasos = "\n".join(f"{i}. {p}" for i, p in enumerate(d["pasos_reproducir"], 1))
    evid = "\n".join(f"- {x}" for x in d["evidencia"])
    aviso = "" if d["es_defecto_real"] else ("\n> Nota: la IA considera que NO es un defecto real del sistema "
                                             "(caso preparado para fallar o problema de datos). Revisar antes de registrarlo.\n")
    return f"""# {d['id']} · {d['titulo']}
{aviso}
| Campo | Valor |
|---|---|
| Caso de prueba | {d['caso']} |
| Módulo | {d['modulo']} |
| Severidad | {d['severidad']} |
| Prioridad | {d['prioridad']} |
| Estado | Nuevo |
| Detectado | {d['fecha']} |
| Ambiente | {d['ambiente']} |

**Justificación de la severidad:** {d['justificacion']}

**Precondiciones:** {d['precondiciones']}

**Datos de prueba:** {d['datos']}

## Pasos para reproducir
{pasos}

## Resultado esperado
{d['resultado_esperado']}

## Resultado obtenido
{d['resultado_obtenido']}

{('**Paso que falló en la automatización:** ' + d['paso_fallido']) if d['paso_fallido'] else ''}

## Evidencia
{evid}

## Causa probable (hipótesis)
{d['causa_probable']}

## Recomendación
{d['recomendacion']}

_Redactado por {d['redactado_por']}. Revisar antes de registrarlo._
"""


def _simulado_defecto(c, malo):
    controlado = "controlado" in c["nombre"].lower()
    return {"titulo": c["nombre"].replace("[FAIL controlado] ", "")[:90],
            "severidad": "Baja" if controlado else "Media", "prioridad": "Baja" if controlado else "Media",
            "justificacion": "Reporte simulado (sin clave de IA): la severidad debe revisarla el tester.",
            "pasos_reproducir": [p["accion"] for p in c.get("pasos", [])],
            "resultado_obtenido": (malo or {}).get("observado") or c.get("observacion", ""),
            "causa_probable": "Sin IA configurada no se propone causa.",
            "recomendacion": "Revisar el paso fallido y su captura.", "es_defecto_real": not controlado}


# ---------------------------------------------------------------- modo simulado (sin clave)
def _simulado_analisis(caso):
    alerta = "alerta" in caso.lower()
    return {"titulo": "Ver alertas pendientes en el módulo Alertas" if alerta else "Buscar un recluso por apellido",
            "ambiguedades": [{"duda": "No se indica con qué rol se ingresa", "supuesto": "Se usa el rol operador"},
                             {"duda": "No se indica qué dato exacto se espera ver",
                              "supuesto": "Se verifica un dato de demostración conocido"}],
            "rol": "operador", "modulo": "Alertas" if alerta else "Reclusos",
            "objetivo": "Verificar el flujo descrito por el usuario en el panel.",
            "precondiciones": "SIBIO-RFID encendido con datos de demostración.",
            "datos": "Alertas de demostración" if alerta else "Apellido 'Quispe' (SP-0412)",
            "resultado_esperado": "Se muestra la pantalla de Alertas" if alerta else "La lista muestra SP-0412",
            "gherkin": ("Característica: Alertas\n  Escenario: Operador revisa alertas\n    Dado que el operador inició sesión\n"
                        "    Cuando abre el módulo Alertas\n    Entonces ve la lista de alertas" if alerta else
                        "Característica: Reclusos\n  Escenario: Buscar por apellido\n    Dado que el operador inició sesión\n"
                        "    Cuando busca 'Quispe' en Reclusos\n    Entonces ve al recluso SP-0412")}


def _simulado_codigo(analisis):
    if analisis.get("modulo") == "Alertas":
        cod = ('entrar(pagina, registro, "operador")\nir_a(pagina, registro, "Alertas")\n'
               'with registro.paso("Verificar que la pantalla de Alertas está abierta") as p:\n'
               '    expect(pagina.get_by_role("heading", name="Alertas").first).to_be_visible()\n'
               '    p["observado"] = "Título Alertas visible"')
    else:
        cod = ('entrar(pagina, registro, "operador")\nir_a(pagina, registro, "Reclusos")\n'
               'with registro.paso("Escribir Quispe en el buscador") as p:\n'
               '    pagina.get_by_label("Buscar reclusos").fill("Quispe")\n'
               '    p["observado"] = "Búsqueda escrita"\n'
               'with registro.paso("Verificar que aparece SP-0412") as p:\n'
               '    expect(pagina.get_by_text("SP-0412").first).to_be_visible()\n'
               '    p["observado"] = "SP-0412 visible"')
    return {"codigo": cod, "locators_usados": [], "nota": "Código fijo del modo simulado."}
