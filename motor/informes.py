"""Genera los dos adjuntos: informe HTML independiente (tabla resumen) e informe PDF detallado por caso."""
import base64
import math
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env = Environment(loader=FileSystemLoader(os.path.join(RAIZ, "plantillas")), autoescape=select_autoescape())

ICONO = {"PASS": "✔", "FAIL": "✖", "ERROR": "⚠", "SKIPPED": "⤼", "NOT RUN": "○"}
TEXTO = {"PASS": "Aprobado", "FAIL": "Fallo funcional", "ERROR": "Error de infraestructura",
         "SKIPPED": "Omitido", "NOT RUN": "No ejecutado"}


COLOR = {"PASS": "#2fd08a", "FAIL": "#ff5a63", "ERROR": "#ffb02e", "SKIPPED": "#9ea3ff", "NOT RUN": "#8b93a5"}


def dona(r, tam=150, texto="#fff"):
    """Gráfica de dona (SVG) con el reparto de estados; va en la portada del PDF."""
    total = r.get("total") or 1
    con_resultado = r.get("PASS", 0) + r.get("FAIL", 0) + r.get("ERROR", 0)
    aprob = round(r.get("PASS", 0) / con_resultado * 100) if con_resultado else 0
    radio, largo, desde, arcos = 54, 2 * math.pi * 54, 0.0, []
    for k in ("PASS", "FAIL", "ERROR", "SKIPPED", "NOT RUN"):
        n = r.get(k, 0)
        if n:
            tramo = n / total * largo
            arcos.append(f'<circle cx="75" cy="75" r="{radio}" fill="none" stroke="{COLOR[k]}" stroke-width="17" '
                         f'stroke-dasharray="{tramo:.2f} {largo - tramo:.2f}" stroke-dashoffset="{-desde:.2f}" transform="rotate(-90 75 75)"/>')
            desde += tramo
    return Markup(f'<svg width="{tam}" height="{tam}" viewBox="0 0 150 150">'
                  f'<circle cx="75" cy="75" r="{radio}" fill="none" stroke="rgba(128,128,128,.25)" stroke-width="17"/>{"".join(arcos)}'
                  f'<text x="75" y="74" text-anchor="middle" font-size="27" font-weight="700" fill="{texto}">{aprob}%</text>'
                  f'<text x="75" y="92" text-anchor="middle" font-size="10" fill="{texto}" opacity=".75">aprobados</text></svg>')


def grafica(g, ancho=680, alto=210):
    """Gráfica de líneas (SVG) de una prueba de carga: tiempos de respuesta y umbral."""
    if not g or not g.get("valores"):
        return ""
    series = [g["valores"]] + ([g["valores2"]] if g.get("valores2") else [])
    tope = max([max(s) for s in series] + [g.get("umbral") or 0, 1]) * 1.1
    x0, y0, w, h = 44, 12, ancho - 56, alto - 44
    colores, nombres = ["#2563eb", "#f59e0b"], g.get("nombres") or ["Tiempo de respuesta (ms)"]
    partes = []
    for i in range(5):
        y = y0 + h - h * i / 4
        partes.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="#e3e7ef"/>'
                      f'<text x="{x0 - 6}" y="{y + 3:.1f}" text-anchor="end" font-size="9" fill="#667">{round(tope * i / 4)}</text>')
    for s, color in zip(series, colores):
        paso = w / max(len(s) - 1, 1)
        pts = " ".join(f"{x0 + i * paso:.1f},{y0 + h - (v / tope) * h:.1f}" for i, v in enumerate(s))
        partes.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round"/>')
    if g.get("umbral"):
        y = y0 + h - g["umbral"] / tope * h
        partes.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="#c0262d" stroke-dasharray="5 4"/>'
                      f'<text x="{x0 + w}" y="{y - 4:.1f}" text-anchor="end" font-size="9" fill="#c0262d">umbral {g["umbral"]} ms</text>')
    leyenda = "".join(f'<rect x="{x0 + i * 170}" y="{alto - 12}" width="12" height="3" fill="{colores[i]}"/>'
                      f'<text x="{x0 + 17 + i * 170}" y="{alto - 8}" font-size="9" fill="#445">{escape(n)}</text>'
                      for i, n in enumerate(nombres[:len(series)]))
    eje = f'<text x="{x0 + w}" y="{alto - 8}" text-anchor="end" font-size="9" fill="#667">{len(series[0])} puntos · eje: {escape(g.get("eje", ""))}</text>'
    return Markup(f'<div class="grafica"><b>{escape(g.get("titulo", ""))}</b>'
                  f'<svg width="100%" viewBox="0 0 {ancho} {alto}">{"".join(partes)}{leyenda}{eje}</svg></div>')


def conclusiones(e):
    """Conclusiones calculadas con los datos de la ejecución (sin IA): siempre aparecen en el PDF."""
    r, casos = e.get("resumen", {}), e["casos"]
    ejecutados = r.get("PASS", 0) + r.get("FAIL", 0)
    out = [f"Se ejecutaron {ejecutados} de {r.get('total', len(casos))} casos y {r.get('PASS', 0)} aprobaron: "
           f"{r.get('exito_pct', 0)} % de éxito sobre los casos ejecutados."]
    fallos = [c for c in casos if c["estado"] == "FAIL"]
    if fallos:
        out.append("Fallos funcionales (el sistema no hizo lo esperado): " + "; ".join(
            f"{c['id']}" + (f" en el paso {c['paso_fallido']}" if c.get("paso_fallido") else "") for c in fallos) + ". Requieren revisión del equipo de desarrollo.")
    else:
        out.append("No se encontró ningún fallo funcional en los casos ejecutados.")
    infra = [c["id"] for c in casos if c["estado"] == "ERROR"]
    if infra:
        out.append("Errores de infraestructura (no son defectos del sistema, la prueba no pudo correr): " + ", ".join(infra) + ". Conviene revisar el entorno y repetirlos.")
    omit = [c["id"] for c in casos if c["estado"] in ("SKIPPED", "NOT RUN")]
    if omit:
        out.append("Casos sin resultado (omitidos o no ejecutados): " + ", ".join(omit) + ". No cuentan para el porcentaje de éxito.")
    con_tiempo = [c for c in casos if isinstance(c.get("duracion_s"), (int, float))]
    if con_tiempo:
        lento = max(con_tiempo, key=lambda c: c["duracion_s"])
        out.append(f"El caso más lento fue {lento['id']} con {lento['duracion_s']} s; la ejecución completa duró {e.get('duracion_s')} s.")
    if not fallos and not infra:
        veredicto = "APTA: la versión probada cumple los casos ejecutados."
    elif fallos:
        veredicto = "EN RIESGO: hay fallos funcionales que deben corregirse antes de liberar."
    else:
        veredicto = "NO CONCLUYENTE: hubo errores de entorno; se debe repetir la ejecución."
    return {"puntos": out, "veredicto": veredicto, "clase": "PASS" if veredicto.startswith("APTA") else "FAIL" if fallos else "ERROR"}


def _b64(ruta):
    if not ruta or not os.path.exists(ruta):
        return None
    with open(ruta, "rb") as fh:
        return ("data:image/jpeg;base64," if ruta.endswith(".jpg") else "data:image/png;base64,") + base64.b64encode(fh.read()).decode()


def _contexto(e, con_capturas):
    casos = []
    for c in e["casos"]:
        pasos = [{**p, "img": _b64(p.get("captura")) if con_capturas else None} for p in c.get("pasos", [])]
        casos.append({**c, "pasos": pasos})
    return {"e": e, "casos": casos, "r": e.get("resumen", {}), "ICONO": ICONO, "TEXTO": TEXTO,
            "dona": dona, "grafica": grafica, "concl": conclusiones(e)}


def generar(e):
    salida = e["salida"]
    os.makedirs(salida, exist_ok=True)
    base = f"Reporte-{e['id']}"
    ruta_html = os.path.join(salida, base + ".html")
    with open(ruta_html, "w", encoding="utf-8") as fh:
        fh.write(_env.get_template("informe_resumen.html").render(**_contexto(e, con_capturas=False)))
    ruta_pdf_html = os.path.join(salida, "_pdf.html")
    with open(ruta_pdf_html, "w", encoding="utf-8") as fh:
        fh.write(_env.get_template("informe_pdf.html").render(**_contexto(e, con_capturas=True)))
    ruta_pdf = os.path.join(salida, base + ".pdf")
    _html_a_pdf(ruta_pdf_html, ruta_pdf, e)
    os.remove(ruta_pdf_html)   # temporal: pesa mucho por las capturas incrustadas
    return {"html": os.path.basename(ruta_html), "pdf": os.path.basename(ruta_pdf)}


def _html_a_pdf(origen, destino, e):
    from playwright.sync_api import sync_playwright
    opciones = {}
    if os.environ.get("CHROMIUM_PATH"):
        opciones["executable_path"] = os.environ["CHROMIUM_PATH"]
    with sync_playwright() as pw:
        b = pw.chromium.launch(**opciones)
        p = b.new_page()
        p.goto("file://" + os.path.abspath(origen))
        p.wait_for_load_state("networkidle")
        pie = (f'<div style="font-size:8px;width:100%;padding:0 14mm;color:#667;display:flex;justify-content:space-between">'
               f'<span>Proyecto de Automatización TQA · SIBIO-RFID · {e["id"]}</span>'
               f'<span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>')
        p.pdf(path=destino, format="A4", print_background=True, display_header_footer=True,
              header_template="<div></div>", footer_template=pie,
              margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        b.close()
