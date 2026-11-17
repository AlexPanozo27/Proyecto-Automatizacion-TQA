"""Acciones comunes del panel para las pruebas E2E (también las usa el código que genera la IA)."""
from playwright.sync_api import expect

from conftest import ADMIN, OPERADOR, SIBIO_URL, SUPERVISOR
from soporte import aviso_2fa, codigo_2fa, nota_espera_2fa

USUARIOS = {"administrador": ADMIN, "operador": OPERADOR, "supervisor": SUPERVISOR}


def escribir_2fa_si_pide(pagina, registro=None):
    """Si el panel muestra la pantalla del código de la app autenticadora, escribe el código actual."""
    campo = pagina.locator("input[inputmode=numeric]").first
    menu = pagina.get_by_role("navigation")
    for _ in range(40):
        if menu.count() and menu.first.is_visible():
            return False
        if campo.count() and campo.is_visible():
            break
        pagina.wait_for_timeout(250)
    else:
        return False
    def escribir():
        codigo = codigo_2fa(aviso_2fa(registro))
        campo.click()
        pagina.keyboard.type(codigo, delay=40)
        return codigo
    if registro:
        with registro.paso("Escribir el código de 6 dígitos del autenticador (2FA)") as p:
            escribir()
            p["observado"] = "Código escrito; el panel lo verifica solo al completar los 6 dígitos" + nota_espera_2fa()
    else:
        escribir()
    return True


def entrar(pagina, registro, rol="administrador"):
    """Abre el panel e inicia sesión con el usuario de pruebas del rol indicado (con 2FA si lo pide)."""
    usuario, clave = USUARIOS[rol]
    with registro.paso(f"Abrir el panel y escribir usuario y contraseña ({rol}: {usuario})") as p:
        pagina.goto(SIBIO_URL + "/")
        expect(pagina.locator("#u")).to_be_visible()
        pagina.wait_for_timeout(600)
        pagina.fill("#u", usuario)
        pagina.fill("#c", clave)
        pagina.locator("button[type=submit]").first.click()
        p["observado"] = "Formulario enviado"
    escribir_2fa_si_pide(pagina, registro)
    with registro.paso("Verificar que se entró al sistema (menú lateral visible)") as p:
        expect(pagina.get_by_role("navigation")).to_be_visible()
        pagina.wait_for_timeout(800)
        p["observado"] = "Sesión iniciada; menú lateral visible"


def ir_a(pagina, registro, modulo):
    """Abre un módulo desde el menú lateral, por su nombre visible (p. ej. 'Reclusos')."""
    with registro.paso(f"Abrir el módulo '{modulo}' desde el menú") as p:
        pagina.get_by_role("navigation").get_by_text(modulo, exact=True).first.click()
        pagina.wait_for_timeout(1000)
        p["observado"] = f"Módulo '{modulo}' abierto"
