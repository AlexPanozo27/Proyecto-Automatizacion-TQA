"""
TC-E2E-01 / TC-E2E-02 implementados también con Selenium WebDriver (complemento de la versión Playwright).

La herramienta principal del proyecto es Playwright (ver README). Este script muestra el mismo caso con
Selenium WebDriver: localizadores By.ID / By.CSS_SELECTOR / By.XPATH, esperas explícitas y aserciones.

Ejecutar (SIBIO encendido), desde la carpeta del proyecto:
    pytest complementos/selenium -v
Variables (.env): SIBIO_URL, SIBIO_OPERADOR, SIBIO_OPERADOR_CLAVE; SELENIUM_NAVEGADOR=edge|chrome (edge por
defecto en Windows); SELENIUM_OCULTO=1 para correr sin ventana. Selenium Manager descarga el driver solo.
Capturas: reportes/selenium/.
"""
import os

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

URL = os.environ.get("SIBIO_URL", "http://127.0.0.1:5000")
USUARIO = os.environ.get("SIBIO_OPERADOR", "jperez")
CLAVE = os.environ.get("SIBIO_OPERADOR_CLAVE", "")
CAPTURAS = os.path.join(os.path.dirname(__file__), "..", "..", "reportes", "selenium")


@pytest.fixture
def driver():
    nav = os.environ.get("SELENIUM_NAVEGADOR", "edge" if os.name == "nt" else "chrome").lower()
    oculto = os.environ.get("SELENIUM_OCULTO", "0") == "1"
    if nav == "edge":
        op = webdriver.EdgeOptions()
    else:
        op = webdriver.ChromeOptions()
        if os.environ.get("CHROMIUM_PATH") and "msedge" not in os.environ["CHROMIUM_PATH"].lower():
            op.binary_location = os.environ["CHROMIUM_PATH"]
    if oculto:
        op.add_argument("--headless=new")
    op.add_argument("--window-size=1366,800")
    op.add_argument("--no-sandbox")
    d = webdriver.Edge(options=op) if nav == "edge" else webdriver.Chrome(options=op)
    d.implicitly_wait(0)
    os.makedirs(CAPTURAS, exist_ok=True)
    yield d
    d.quit()


def _escribir_login(driver, usuario, clave):
    driver.get(URL + "/")
    espera = WebDriverWait(driver, 15)
    campo_usuario = espera.until(EC.visibility_of_element_located((By.ID, "u")))     # localizador por ID
    campo_usuario.clear()
    campo_usuario.send_keys(usuario)
    driver.find_element(By.ID, "c").send_keys(clave)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()               # localizador CSS
    return espera


def test_tc_e2e_01_login_valido_selenium(driver):
    """TC-E2E-01 (Selenium): con credenciales válidas se entra al panel y se ve el menú lateral."""
    espera = _escribir_login(driver, USUARIO, CLAVE)
    menu = espera.until(EC.visibility_of_element_located((By.TAG_NAME, "nav")))
    espera.until(EC.visibility_of_element_located((By.XPATH, "//nav//*[contains(normalize-space(.), 'Reclusos')]")))  # XPath
    driver.save_screenshot(os.path.join(CAPTURAS, "TC-E2E-01-selenium.png"))
    assert menu.is_displayed(), "El menú lateral no se mostró después de iniciar sesión"
    assert "Reclusos" in menu.text, "El menú no muestra el módulo Reclusos"


def test_tc_e2e_02_clave_incorrecta_selenium(driver):
    """TC-E2E-02 (Selenium): con contraseña incorrecta no se entra y aparece un mensaje de error."""
    espera = _escribir_login(driver, USUARIO, "ClaveIncorrecta-123")
    aviso = espera.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[role=alert]")))
    driver.save_screenshot(os.path.join(CAPTURAS, "TC-E2E-02-selenium.png"))
    assert aviso.text.strip(), "El mensaje de error está vacío"
    assert not driver.find_elements(By.TAG_NAME, "nav"), "Entró al sistema con una contraseña incorrecta"
