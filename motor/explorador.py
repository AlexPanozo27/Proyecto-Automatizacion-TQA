"""
Recorre el panel REAL de SIBIO-RFID con Playwright y guarda los elementos que se pueden usar en una prueba
(botones, campos, enlaces del menú, títulos) con su locator. La IA solo puede usar locators de este mapa:
así no inventa botones que no existen.
"""
import json
import os
import time

from motor.ejecutor import REPORTES

ARCHIVO = os.path.join(REPORTES, "mapa_locators.json")
CARPETA_FOTOS = os.path.join(REPORTES, "mapa_pantallas")


def _foto(p, nombre, fotos):
    """Miniatura de la pantalla: la web la muestra junto a los locators verificados."""
    os.makedirs(CARPETA_FOTOS, exist_ok=True)
    archivo = f"pantalla{len(fotos) + 1:02d}.jpg"
    try:
        p.screenshot(path=os.path.join(CARPETA_FOTOS, archivo), type="jpeg", quality=60)
        fotos[nombre] = archivo
    except Exception:  # noqa: BLE001
        pass

_JS = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const limpio = (t) => (t || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  const etiqueta = (e) => { if (e.id) { const l = document.querySelector(`label[for="${e.id}"]`); if (l) return limpio(l.innerText); }
    const l = e.closest('label'); return l ? limpio(l.innerText) : ''; };
  const out = [];
  for (const e of document.querySelectorAll('button, a[href], input, select, textarea, h1, h2, h3, [role=tab], [role=alert]')) {
    if (!vis(e)) continue;
    const tag = e.tagName.toLowerCase();
    let rol = e.getAttribute('role') || ({button: 'button', a: 'link', select: 'combobox', textarea: 'textbox', h1: 'heading', h2: 'heading', h3: 'heading'}[tag]);
    if (tag === 'input') rol = ({checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button'}[e.type] || 'textbox');
    const nombre = limpio(e.getAttribute('aria-label') || etiqueta(e) || e.innerText || e.value || e.getAttribute('title'));
    out.push({rol, nombre, id: e.id || '', placeholder: e.getAttribute('placeholder') || '', en_menu: !!e.closest('nav')});
  }
  return out;
}"""


def _locators(el):
    """Locators de Playwright (Python) para un elemento, del más robusto al menos."""
    loc = []
    if el["id"]:
        loc.append(f'pagina.locator("#{el["id"]}")')
    if el["rol"] == "textbox" and el["nombre"]:
        loc.append(f'pagina.get_by_label("{el["nombre"]}")')
    if el["placeholder"]:
        loc.append(f'pagina.get_by_placeholder("{el["placeholder"]}")')
    if el["nombre"] and el["rol"] in ("button", "link", "heading", "tab", "checkbox", "combobox"):
        loc.append(f'pagina.get_by_role("{el["rol"]}", name="{el["nombre"]}")')
    if el["rol"] == "alert":
        loc.append('pagina.get_by_role("alert")')
    return loc


def explorar(url, usuario, clave):
    from playwright.sync_api import sync_playwright
    opciones = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
    mapa = {"generado": time.strftime("%Y-%m-%d %H:%M:%S"), "url": url, "pantallas": {}}
    with sync_playwright() as pw:
        b = pw.chromium.launch(**opciones)
        p = b.new_page(viewport={"width": 1366, "height": 800})
        p.set_default_timeout(10000)
        p.goto(url + "/")
        p.wait_for_selector("#u")
        p.wait_for_timeout(800)
        fotos = {}
        mapa["pantallas"]["Inicio de sesión"] = p.evaluate(_JS)
        _foto(p, "Inicio de sesión", fotos)
        p.fill("#u", usuario)
        p.fill("#c", clave)
        p.locator("button[type=submit]").first.click()
        campo = p.locator("input[inputmode=numeric]").first
        p.wait_for_selector("nav, input[inputmode=numeric]")
        if campo.count() and campo.is_visible():      # el administrador tiene 2FA: se escribe el código actual
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(REPORTES), "tests"))
            from soporte import codigo_2fa
            campo.click()
            p.keyboard.type(codigo_2fa(), delay=40)
        p.wait_for_selector("nav")
        p.wait_for_timeout(1500)
        import re
        modulos = []
        for x in p.evaluate(_JS):
            m = re.sub(r"\s+\d+$", "", x.get("nombre", "")).strip()   # quita el contador ("Alertas 8")
            if x["en_menu"] and len(m) > 3 and not m.startswith(("Buscar", "Documentación")) and m not in modulos:
                modulos.append(m)
        mapa["menu"] = modulos
        for m in modulos:
            try:
                p.get_by_role("navigation").get_by_text(m, exact=True).first.click(timeout=4000)
                p.wait_for_timeout(1200)
                mapa["pantallas"][m] = [x for x in p.evaluate(_JS) if not x["en_menu"]]
                _foto(p, m, fotos)
            except Exception:  # noqa: BLE001
                continue
        b.close()
    mapa["fotos"] = fotos
    for nombre, elementos in mapa["pantallas"].items():
        vistos, unicos = set(), []
        for el in elementos:
            clave_el = (el["rol"], el["nombre"], el["id"])
            if clave_el in vistos or not (el["nombre"] or el["id"] or el["placeholder"]):
                continue
            vistos.add(clave_el)
            unicos.append({"rol": el["rol"], "nombre": el["nombre"], "locators": _locators(el)})
        mapa["pantallas"][nombre] = unicos[:60]
    os.makedirs(REPORTES, exist_ok=True)
    with open(ARCHIVO, "w", encoding="utf-8") as fh:
        json.dump(mapa, fh, ensure_ascii=False, indent=1)
    return mapa


def cargar():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def texto_para_ia(mapa):
    """El mapa resumido en texto para el prompt."""
    lineas = [f"Módulos del menú (usar con ir_a): {', '.join(mapa.get('menu', []))}"]
    for pantalla, els in mapa["pantallas"].items():
        lineas.append(f"\n## Pantalla: {pantalla}")
        for el in els:
            if el["locators"]:
                lineas.append(f"- {el['rol']} «{el['nombre']}»: " + " | ".join(el["locators"]))
    return "\n".join(lineas)


def todos_los_locators(mapa):
    return {loc for els in mapa["pantallas"].values() for el in els for loc in el["locators"]}


def pantalla_de(mapa):
    """locator → primera pantalla donde aparece."""
    donde = {}
    for nombre, els in mapa["pantallas"].items():
        for el in els:
            for loc in el["locators"]:
                donde.setdefault(loc, nombre)
    return donde
