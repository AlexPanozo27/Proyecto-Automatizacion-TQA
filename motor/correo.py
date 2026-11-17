"""Envío del informe por correo (SMTP). Los datos van en variables de entorno, nunca en el código."""
import html as html_mod
import os
import re
import smtplib
from email.message import EmailMessage

PATRON = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def valido(direccion):
    return bool(direccion) and len(direccion) <= 254 and bool(PATRON.match(direccion.strip()))


def configurado():
    return bool(os.environ.get("SMTP_USUARIO") and os.environ.get("SMTP_CLAVE"))


def asunto(e):
    return f"Reporte de automatización – {e['etiqueta']} – {e['inicio'][:16]}"


def enviar(e):
    if not configurado():
        return False, "SMTP sin configurar (SMTP_USUARIO y SMTP_CLAVE en .env). El informe se puede descargar desde la web."
    r = e["resumen"]
    msg = EmailMessage()
    msg["Subject"] = asunto(e)
    msg["From"] = f"{os.environ.get('SMTP_NOMBRE', 'Automatización TQA')} <{os.environ['SMTP_USUARIO']}>"
    msg["To"] = e["correo"]
    estado = "SIN FALLOS" if r["FAIL"] == 0 and r["ERROR"] == 0 else "CON FALLOS"
    texto = (f"Ejecución {e['id']} ({e['etiqueta']}) terminada: {estado}.\n\n"
             f"Inicio: {e['inicio']}   Fin: {e['fin']}   Duración: {e['duracion_s']} s\n"
             f"Total {r['total']} · PASS {r['PASS']} · FAIL {r['FAIL']} · ERROR {r['ERROR']} · "
             f"SKIPPED {r['SKIPPED']} · NOT RUN {r['NOT RUN']}\n\n"
             "Adjuntos:\n - Informe PDF detallado por caso (pasos, capturas, error y paso fallido)\n"
             " - Informe HTML independiente (tabla resumen)\n"
             + (f"\nAnálisis de fallos con IA:\n{e['resumen_ia']}\n" if e.get("resumen_ia") else ""))
    filas = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #e3e6ec'>{c['id']}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #e3e6ec'>{c['nombre']}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #e3e6ec;font-weight:700;color:"
        f"{ {'PASS': '#0a7d48', 'FAIL': '#c0262d', 'ERROR': '#b25e00'}.get(c['estado'], '#556') }'>{c['estado']}</td></tr>"
        for c in e["casos"])
    html = (f"<div style='font-family:Segoe UI,Arial,sans-serif;color:#1b2230;max-width:640px'>"
            f"<h2 style='margin:0 0 4px'>Reporte de automatización – {e['etiqueta']}</h2>"
            f"<p style='margin:0 0 14px;color:#556'>{e['id']} · {e['inicio']} → {e['fin']} · {e['duracion_s']} s</p>"
            f"<p style='font-size:15px'><b>{estado}</b> — {r['PASS']} PASS, {r['FAIL']} FAIL, {r['ERROR']} ERROR, "
            f"{r['SKIPPED']} SKIPPED, {r['NOT RUN']} NOT RUN de {r['total']} casos.</p>"
            + (f"<div style='border-left:4px solid #6b5bff;background:#f4f3ff;padding:10px 14px;margin:0 0 14px;font-size:13.5px'>"
               f"<b>✦ Análisis de fallos con IA</b><br>{html_mod.escape(e['resumen_ia']).replace(chr(10), '<br>')}</div>"
               if e.get("resumen_ia") else "") +
            f"<table style='border-collapse:collapse;font-size:13px;width:100%'>{filas}</table>"
            f"<p style='color:#556;font-size:12px;margin-top:16px'>Se adjuntan el informe PDF detallado y el HTML independiente.</p></div>")
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    for clave, tipo in (("pdf", ("application", "pdf")), ("html", ("text", "html"))):
        ruta = os.path.join(e["salida"], e["informe"][clave])
        with open(ruta, "rb") as fh:
            msg.add_attachment(fh.read(), maintype=tipo[0], subtype=tipo[1], filename=os.path.basename(ruta))
    try:
        with smtplib.SMTP(os.environ.get("SMTP_SERVIDOR", "smtp.gmail.com"), int(os.environ.get("SMTP_PUERTO", "587")),
                          timeout=30) as s:
            s.starttls()
            s.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_CLAVE"])
            s.send_message(msg)
        return True, f"Enviado a {e['correo']}"
    except Exception as ex:  # noqa: BLE001
        return False, f"No se pudo enviar el correo: {type(ex).__name__}: {ex}"
