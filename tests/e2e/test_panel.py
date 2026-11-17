"""Pruebas extremo a extremo del panel web de SIBIO-RFID con Playwright (una captura por paso)."""
import random

from playwright.sync_api import expect

from ayudas_e2e import entrar, ir_a
from conftest import ADMIN, OPERADOR, SIBIO_URL, SUPERVISOR
from soporte import caso


def _entrar(pagina, registro, usuario, clave):
    with registro.paso("Abrir la página de inicio de sesión del panel") as p:
        pagina.goto(SIBIO_URL + "/")
        expect(pagina.locator("#u")).to_be_visible()
        pagina.wait_for_timeout(900)   # deja terminar la animación de entrada para que la captura sea legible
        p["observado"] = f"Formulario visible en {pagina.url}"
    with registro.paso(f"Escribir el usuario '{usuario}' y la contraseña") as p:
        pagina.fill("#u", usuario)
        pagina.fill("#c", clave)
        p["observado"] = "Campos completados (la contraseña se muestra oculta)"
    with registro.paso("Pulsar el botón Ingresar") as p:
        pagina.locator("button[type=submit]").first.click()
        p["observado"] = "Formulario enviado"


@caso("TC-E2E-01", "Inicio de sesión en el panel y Centro de monitoreo visible", suites=["smoke", "e2e", "regression"],
      modulo="Panel web · Autenticación",
      objetivo="Comprobar de punta a punta que el administrador entra al panel y ve el Centro de monitoreo.",
      precondiciones="SIBIO-RFID encendido con el panel compilado y datos de demostración.",
      datos=f"Usuario {ADMIN[0]} / contraseña y código 2FA de la app autenticadora (si lo tiene)",
      resultado_esperado="Se muestra el título 'Centro de monitoreo' y el KPI 'Reclusos activos'.")
def test_login_panel(pagina, registro):
    entrar(pagina, registro, "administrador")
    with registro.paso("Verificar el título 'Centro de monitoreo'") as p:
        expect(pagina.get_by_role("heading", name="Centro de monitoreo")).to_be_visible()
        p["observado"] = "Título visible"
    with registro.paso("Verificar el indicador 'Reclusos activos'") as p:
        expect(pagina.get_by_text("Reclusos activos", exact=False).first).to_be_visible()
        p["observado"] = "KPI visible"


@caso("TC-E2E-02", "Contraseña incorrecta muestra un mensaje de error claro", suites=["e2e", "sanity", "regression"],
      modulo="Panel web · Autenticación",
      objetivo="Verificar que el panel informa el error sin dejar entrar.",
      precondiciones="SIBIO-RFID encendido.", datos="Usuario aleatorio qa_xxxx con contraseña errónea",
      resultado_esperado="Aparece el aviso 'Usuario o contraseña incorrectos' y se sigue en la pantalla de ingreso.")
def test_login_incorrecto(pagina, registro):
    _entrar(pagina, registro, f"qa_{random.randint(1000, 9999)}", "ClaveIncorrecta1")
    with registro.paso("Verificar el mensaje de error") as p:
        aviso = pagina.get_by_role("alert")
        expect(aviso).to_contain_text("incorrectos")
        p["observado"] = f"Aviso: '{aviso.inner_text().strip()}'"
    with registro.paso("Verificar que no se entró al sistema") as p:
        expect(pagina.locator("#u")).to_be_visible()
        p["observado"] = "El formulario de ingreso sigue visible"


@caso("TC-E2E-03", "Buscar un recluso desde el módulo Reclusos", suites=["e2e", "regression"],
      modulo="Panel web · Reclusos",
      objetivo="Comprobar la navegación al módulo Reclusos y la búsqueda por apellido.",
      precondiciones=f"Operador de pruebas ({OPERADOR[0]}) del penal 1; existe Carlos Quispe Choque (SP-0412).",
      datos="Texto de búsqueda: 'Quispe'",
      resultado_esperado="La lista muestra al recluso con código SP-0412.")
def test_buscar_recluso(pagina, registro):
    entrar(pagina, registro, "operador")
    ir_a(pagina, registro, "Reclusos")
    with registro.paso("Escribir 'Quispe' en el buscador") as p:
        pagina.get_by_label("Buscar reclusos").fill("Quispe")
        pagina.wait_for_timeout(800)
        p["observado"] = "Búsqueda aplicada"
    with registro.paso("Verificar que aparece SP-0412") as p:
        expect(pagina.get_by_text("SP-0412").first).to_be_visible()
        p["observado"] = "SP-0412 visible en la lista"


@caso("TC-E2E-04", "[FAIL controlado] El Centro de monitoreo no debe tener alertas pendientes",
      suites=["e2e", "regression"], modulo="Panel web · Alertas",
      objetivo="Caso preparado A PROPÓSITO para fallar y demostrar cómo se reporta un FAIL: los datos de "
               "demostración siempre tienen alertas pendientes.",
      precondiciones=f"Supervisor de pruebas ({SUPERVISOR[0]}); datos de demostración con alertas pendientes.",
      datos="Valor esperado del KPI 'Alertas pendientes': 0",
      resultado_esperado="FAIL esperado: el KPI muestra un número mayor que 0. Sirve para ver el paso fallido y su captura.")
def test_fail_controlado(pagina, registro):
    entrar(pagina, registro, "supervisor")
    with registro.paso("Leer el KPI 'Alertas pendientes'") as p:
        tarjeta = pagina.locator(".kpi", has_text="Alertas pendientes").first
        expect(tarjeta).to_be_visible()
        pagina.wait_for_timeout(1500)   # el número del KPI sube con una animación; se espera a que termine
        texto = tarjeta.locator(".valor").inner_text().strip()
        valor = int("".join(ch for ch in texto if ch.isdigit()) or -1)
        p["observado"] = f"KPI 'Alertas pendientes' = {valor}"
    with registro.paso("Verificar que el KPI es 0 (FAIL controlado)") as p:
        assert valor == 0, f"se esperaban 0 alertas pendientes y el panel muestra {valor}"
