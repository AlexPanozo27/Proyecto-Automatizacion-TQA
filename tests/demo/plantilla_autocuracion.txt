"""Demostración de autocuración con IA.
Este caso se escribió para una versión anterior del panel, cuando el buscador de Reclusos se llamaba
"Buscar internos". Hoy se llama "Buscar reclusos", así que el caso falla con ERROR del script.
En la web, "Reparar con IA" propone el locator nuevo (solo entre los que existen en el panel real),
tú lo apruebas, se corrige el archivo y el caso se vuelve a ejecutar.
Para repetir la demostración: botón "Restaurar demo" en la web (vuelve a poner el locator antiguo).
No forma parte de Smoke, Regresión ni E2E: solo de la suite "Autocuración (demo IA)".
"""
from playwright.sync_api import expect

from ayudas_e2e import entrar, ir_a
from conftest import OPERADOR
from soporte import caso


@caso("TC-AC-01", "[Demo autocuración] Buscar recluso con un locator de una versión anterior del panel",
      suites=["autocuracion"], modulo="Panel web · Reclusos",
      objetivo="Mostrar cómo la IA repara una prueba cuando cambia el nombre de un campo del panel.",
      precondiciones=f"Operador de pruebas ({OPERADOR[0]}); existe Carlos Quispe Choque (SP-0412).",
      datos="Texto de búsqueda: 'Quispe'",
      resultado_esperado="Antes de reparar: ERROR del script (el campo 'Buscar internos' ya no existe). "
                         "Después de reparar con IA: PASS, la lista muestra SP-0412.")
def test_autocuracion_demo(pagina, registro):
    entrar(pagina, registro, "operador")
    ir_a(pagina, registro, "Reclusos")
    with registro.paso("Escribir 'Quispe' en el buscador de reclusos") as p:
        pagina.get_by_label("Buscar internos").fill("Quispe")
        pagina.wait_for_timeout(800)
        p["observado"] = "Búsqueda aplicada"
    with registro.paso("Verificar que aparece SP-0412") as p:
        expect(pagina.get_by_text("SP-0412").first).to_be_visible()
        p["observado"] = "SP-0412 visible en la lista"
