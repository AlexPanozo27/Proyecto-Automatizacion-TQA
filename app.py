"""
Plataforma web de automatización de pruebas (TQA) para SIBIO-RFID.
    python app.py      →  http://127.0.0.1:8080
"""
import os

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor import correo, ejecutor  # noqa: E402

app = Flask(__name__, static_folder="web", static_url_path="/web")


@app.get("/")
def inicio():
    return send_from_directory("web", "index.html")


@app.get("/api/catalogo")
def catalogo():
    return jsonify(suites=ejecutor.SUITES, casos=ejecutor.catalogo(request.args.get("refrescar") == "1"),
                   smtp=correo.configurado(), sibio=os.environ.get("SIBIO_URL", "http://127.0.0.1:5000"),
                   navegador_visible=ejecutor.navegador_visible())


@app.get("/api/salud")
def salud():
    """¿Está encendido el sistema bajo prueba? Se muestra arriba en la web."""
    import requests
    url = os.environ.get("SIBIO_URL", "http://127.0.0.1:5000")
    try:
        r = requests.get(url + "/api/auth/opciones", timeout=3)
        return jsonify(sibio=r.status_code < 500, url=url, ms=round(r.elapsed.total_seconds() * 1000))
    except requests.RequestException:
        return jsonify(sibio=False, url=url, ms=None)


@app.post("/api/ejecuciones")
def crear():
    d = request.get_json(silent=True) or {}
    tipo = d.get("tipo") if d.get("tipo") in ejecutor.SUITES else None
    suite = (d.get("suite") or "").strip()
    casos = [c for c in (d.get("casos") or []) if isinstance(c, str)]
    direccion = (d.get("correo") or "").strip()
    if not tipo:
        return jsonify(error="Elija el tipo de prueba: funcional o no funcional"), 400
    if not casos and suite not in [s for s, _ in ejecutor.SUITES[tipo]]:
        return jsonify(error="Elija una suite o al menos un caso"), 400
    if not correo.valido(direccion):
        return jsonify(error="Escriba un correo válido, por ejemplo nombre@gmail.com"), 400
    try:
        e = ejecutor.crear(tipo, suite, casos, direccion, d.get("velocidad") or "normal")
    except ValueError as ex:
        return jsonify(error=str(ex)), 400
    return jsonify(ejecutor.publico(e)), 201


@app.get("/api/ejecuciones")
def historial():
    return jsonify(ejecutor.historial())


@app.get("/api/ejecuciones/<eid>")
def ver(eid):
    e = ejecutor.obtener(eid)
    if not e:
        abort(404)
    return jsonify(ejecutor.publico(e))


@app.post("/api/ejecuciones/<eid>/cancelar")
def cancelar(eid):
    return jsonify(ok=ejecutor.cancelar(eid))


@app.post("/api/ejecuciones/<eid>/casos/<cid>/defecto")
def redactar_defecto(eid, cid):
    """La IA redacta el reporte de defecto (bug report) de un caso que terminó en FAIL."""
    from motor import ia
    e = ejecutor.obtener(eid)
    c = e and next((x for x in e["casos"] if x["id"] == cid), None)
    if not c:
        abort(404)
    if c["estado"] != "FAIL":
        return jsonify(error="Solo se redacta un reporte de defecto para casos en FAIL (fallo funcional). "
                             "Un ERROR es un problema del entorno, no un defecto de SIBIO."), 400
    ya = (e.get("defectos") or {}).get(cid)
    if ya and request.args.get("de_nuevo") != "1":
        return jsonify(ya)
    try:
        reporte = ia.reporte_defecto(e, c)
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=str(ex)), 502
    return jsonify(ejecutor.guardar_defecto(e["id"], cid, reporte)), 201


@app.post("/api/ejecuciones/<eid>/casos/<cid>/reparar")
def reparar(eid, cid):
    """Autocuración: la IA propone el locator nuevo para un caso que falló porque un elemento ya no aparece."""
    from motor import ia
    e = ejecutor.obtener(eid)
    c = e and next((x for x in e["casos"] if x["id"] == cid), None)
    if not c:
        abort(404)
    try:
        return jsonify(ia.proponer_reparacion(e, c, _mapa()))
    except ia.SinReparacion as ex:
        return jsonify(error=str(ex)), 400
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=str(ex)), 502


@app.post("/api/autocuracion/aplicar")
def aplicar_reparacion():
    """Aplica la reparación aprobada por el tester y vuelve a ejecutar ese caso."""
    from motor import ia
    d = request.get_json(silent=True) or {}
    cid, origen = d.get("caso", ""), ejecutor.obtener(d.get("ejecucion", "")) or {}
    try:
        ia.aplicar_reparacion(cid, d.get("roto", ""), d.get("nuevo", ""), _mapa())
    except ia.SinReparacion as ex:
        return jsonify(error=str(ex)), 400
    ejecutor.catalogo(refrescar=True)
    e = ejecutor.crear("funcional", "", [cid], origen.get("correo") or "", origen.get("velocidad") or "normal")
    return jsonify(ejecutor.publico(e)), 201


@app.post("/api/autocuracion/restaurar-demo")
def restaurar_demo():
    from motor import ia
    ia.restaurar_demo()
    return jsonify(ok=True)


@app.post("/api/jarvis")
def jarvis():
    """Chat con Jarvis: sabe del proyecto, de teoría QA y de los resultados reales."""
    from motor import ia, jarvis as j
    d = request.get_json(silent=True) or {}
    try:
        modo = d.get("modo") if d.get("modo") in ("auto", "rapido", "potente") else "auto"
        return jsonify(j.responder(d.get("mensaje"), d.get("historial") or [], d.get("ejecucion") or None, modo,
                                     str(d.get("nombre") or "")))
    except ia.ErrorIA as ex:
        return jsonify(error=str(ex)), 502
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=f"Jarvis no pudo responder: {ex}"), 500


# ---------------- Asistente de IA ----------------
def _sibio():
    return (os.environ.get("SIBIO_URL", "http://127.0.0.1:5000"), os.environ.get("SIBIO_ADMIN", "admin"),
            os.environ.get("SIBIO_ADMIN_CLAVE", ""))


@app.get("/api/ia/estado")
def ia_estado():
    from motor import explorador, ia
    mapa = explorador.cargar()
    return jsonify(**ia.estado(), mapa=bool(mapa), mapa_fecha=mapa and mapa.get("generado"),
                   resumen_pantallas=[{"nombre": k, "n": len(v), "foto": (mapa.get("fotos") or {}).get(k)}
                                      for k, v in mapa["pantallas"].items()] if mapa else [],
                   pantallas=len(mapa["pantallas"]) if mapa else 0,
                   locators=len(explorador.todos_los_locators(mapa)) if mapa else 0)


@app.post("/api/ia/explorar")
def ia_explorar():
    from motor import explorador
    try:
        mapa = explorador.explorar(*_sibio())
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=f"No se pudo recorrer el panel de SIBIO: {ex}"), 502
    return jsonify(mapa_fecha=mapa["generado"], pantallas=len(mapa["pantallas"]),
                   locators=len(explorador.todos_los_locators(mapa)))


@app.get("/api/ia/pantalla/<archivo>")
def ia_pantalla(archivo):
    from motor import explorador
    return send_from_directory(explorador.CARPETA_FOTOS, archivo)


def _mapa():
    from motor import explorador
    return explorador.cargar() or explorador.explorar(*_sibio())


@app.post("/api/ia/analizar")
def ia_analizar():
    from motor import ia
    caso = ((request.get_json(silent=True) or {}).get("caso") or "").strip()
    if len(caso) < 15:
        return jsonify(error="Describa el caso con un poco más de detalle (qué hace el usuario y qué debe ver)"), 400
    try:
        return jsonify({**ia.analizar(caso[:3000], _mapa()), "_ia": dict(ia.ULTIMO)})
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=str(ex)), 502


@app.post("/api/ia/generar")
def ia_generar():
    from motor import ia
    analisis = (request.get_json(silent=True) or {}).get("analisis") or {}
    try:
        mapa = _mapa()
        r = ia.generar_codigo(analisis, mapa)
        return jsonify(**r, revision=ia.revisar(r.get("codigo", ""), mapa), _ia=dict(ia.ULTIMO))
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=str(ex)), 502


@app.post("/api/ia/revisar")
def ia_revisar():
    from motor import ia
    return jsonify(ia.revisar((request.get_json(silent=True) or {}).get("codigo", ""), _mapa()))


@app.post("/api/ia/guardar")
def ia_guardar():
    from motor import ia
    d = request.get_json(silent=True) or {}
    rev = ia.revisar(d.get("codigo", ""), _mapa())
    if not rev["ok"]:
        return jsonify(error="El código no pasó la revisión", revision=rev), 400
    try:
        cid = ia.guardar(d.get("analisis") or {}, rev["codigo"], d.get("caso", ""))
    except Exception as ex:  # noqa: BLE001
        return jsonify(error=f"No se pudo guardar: {ex}"), 500
    ejecutor.catalogo(refrescar=True)
    return jsonify(id=cid), 201


@app.get("/reportes/<eid>/<path:archivo>")
def descargar(eid, archivo):
    e = ejecutor.obtener(eid)
    if not e:
        abort(404)
    return send_from_directory(os.path.join(ejecutor.REPORTES, e["id"]), archivo,
                               as_attachment=request.args.get("descargar") == "1")


if __name__ == "__main__":
    from waitress import serve
    puerto = int(os.environ.get("QA_PUERTO", "8080"))
    print(f"\n  Plataforma de automatización TQA lista en http://127.0.0.1:{puerto}\n")
    serve(app, host=os.environ.get("QA_HOST", "127.0.0.1"), port=puerto, threads=8)
