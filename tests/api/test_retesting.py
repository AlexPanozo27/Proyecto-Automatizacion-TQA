"""Retesting: vuelve a ejecutar los defectos reportados en el Entregable 1 (28/10/2026, BUG-001 a BUG-005).

Cada caso comprueba el comportamiento CORRECTO que pedía el bug report. Mientras el defecto siga abierto, el caso
da FAIL (fallo funcional real del sistema, no de la prueba). Cuando se corrija SIBIO, este mismo caso dará PASS y
el defecto se podrá cerrar. Suite propia "retest", separada de la regresión.
"""
import random
import time

from soporte import caso


def _cod():
    return "RT-" + time.strftime("%H%M%S") + str(random.randint(10, 99))


def _lector(sibio, token):
    r = sibio.llamar("POST", "/api/puntos-control", token, recinto=1,
                     json={"nombre": "Lector retest " + _cod(), "tipo": "interno", "zona_id": 1})
    assert r.status_code in (200, 201) and r.datos.get("api_key"), f"no se pudo crear el lector simulado (HTTP {r.status_code})"
    return r.datos["api_key"]


@caso("TC-RT-01", "Retest BUG-001: el CI del recluso no acepta letras ni símbolos", suites=["retest"],
      modulo="Reclusos", objetivo="Verificar si BUG-001 (CI acepta letras y símbolos) ya fue corregido.",
      precondiciones="SIBIO-RFID encendido; sesión de administrador.",
      datos="ci='ABC-$%&' (clase inválida de la partición de equivalencia del CI)",
      resultado_esperado="HTTP 400 con un mensaje que indique que el CI es inválido.")
def test_retest_bug001_ci(sibio, token_admin, registro):
    with registro.paso("Registrar un recluso con CI 'ABC-$%&'") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": _cod(), "nombres": "Retest", "apellidos": "Ci Invalido", "ci": "ABC-$%&"})
        p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or ''}".strip()
        assert r.status_code == 400, f"BUG-001 sigue abierto: el CI 'ABC-$%&' se aceptó (HTTP {r.status_code})"


@caso("TC-RT-02", "Retest BUG-002: estado y fecha de nacimiento fuera de dominio son rechazados", suites=["retest"],
      modulo="Reclusos", objetivo="Verificar si BUG-002 (estado y fecha fuera de dominio aceptados) ya fue corregido.",
      precondiciones="SIBIO-RFID encendido; sesión de administrador.",
      datos="estado='volando'; fecha_nacimiento=2090-01-01 (valor límite: fecha futura)",
      resultado_esperado="HTTP 400 en los dos registros.")
def test_retest_bug002_dominio(sibio, token_admin, registro):
    with registro.paso("Registrar un recluso con estado 'volando'") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": _cod(), "nombres": "Retest", "apellidos": "Estado", "estado": "volando"})
        p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or ''}".strip()
        assert r.status_code == 400, f"estado fuera de dominio aceptado (HTTP {r.status_code})"
    with registro.paso("Registrar un recluso con fecha de nacimiento 2090-01-01") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": _cod(), "nombres": "Retest", "apellidos": "Fecha", "fecha_nacimiento": "2090-01-01"})
        p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or ''}".strip()
        assert r.status_code == 400, f"BUG-002 sigue abierto en parte: la fecha futura se aceptó (HTTP {r.status_code})"


@caso("TC-RT-03", "Retest BUG-003: UID RFID incompleto (3 bytes o dígitos impares) es rechazado", suites=["retest"],
      modulo="Manillas RFID", objetivo="Verificar si BUG-003 (UID incompletos aceptados) ya fue corregido.",
      precondiciones="SIBIO-RFID encendido; sesión de administrador.",
      datos="UID hexadecimal aleatorio de 6 dígitos (3 bytes) y de 7 dígitos (impar); válido = 8 dígitos (4 bytes)",
      resultado_esperado="HTTP 400 'Código RFID inválido' para los dos.")
def test_retest_bug003_uid(sibio, token_admin, registro):
    for n in (6, 7):
        uid = "".join(random.choice("0123456789ABCDEF") for _ in range(n))   # aleatorio: no choca con corridas previas
        with registro.paso(f"Registrar una manilla con UID '{uid}' ({len(uid)} dígitos)") as p:
            r = sibio.llamar("POST", "/api/manillas", token_admin, recinto=1, json={"codigo_rfid": uid})
            p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or r.datos.get('codigo_rfid') or ''}".strip()
            assert r.status_code == 400, f"BUG-003 sigue abierto: el UID '{uid}' se aceptó (HTTP {r.status_code})"


@caso("TC-RT-04", "Retest BUG-004: pulso no numérico se rechaza con 400 y no con error 500", suites=["retest"],
      modulo="Telemetría / Alertas", objetivo="Verificar si BUG-004 (bpm 'abc' provoca HTTP 500) ya fue corregido.",
      precondiciones="SIBIO-RFID encendido; manilla A3:5F:12:9C asignada (datos de demostración); lector simulado.",
      datos="bpm='abc' (tipo inválido) y luego bpm=72 (válido)",
      resultado_esperado="HTTP 400 para 'abc' y HTTP 200 para la lectura válida siguiente.")
def test_retest_bug004_bpm(sibio, token_admin, registro):
    clave = _lector(sibio, token_admin)
    with registro.paso("El lector envía telemetría con bpm='abc'") as p:
        r = sibio.llamar("POST", "/api/dispositivos/telemetria", clave_lector=clave,
                         json={"codigo_rfid": "A3:5F:12:9C", "bpm": "abc", "contacto": True, "bateria": 90})
        malo = r.status_code
        p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or ''}".strip()
    with registro.paso("El lector envía una lectura válida (bpm=72) justo después") as p:
        r = sibio.llamar("POST", "/api/dispositivos/telemetria", clave_lector=clave,
                         json={"codigo_rfid": "A3:5F:12:9C", "bpm": 72, "contacto": True, "bateria": 90})
        p["observado"] = f"HTTP {r.status_code}"
        assert r.status_code == 200, f"la lectura válida falló después del dato inválido (HTTP {r.status_code})"
    with registro.paso("Comprobar que el dato inválido se rechazó con 400 (no 500)") as p:
        p["observado"] = f"bpm='abc' respondió HTTP {malo}"
        assert malo == 400, f"BUG-004 sigue abierto: bpm='abc' responde HTTP {malo} en lugar de 400"


@caso("TC-RT-05", "Retest BUG-005: batería mayor a 100 % es rechazada", suites=["retest"],
      modulo="Telemetría / Manillas", objetivo="Verificar si BUG-005 (batería > 100 % aceptada) ya fue corregido.",
      precondiciones="SIBIO-RFID encendido; manilla A3:5F:12:9C asignada; lector simulado.",
      datos="bateria=250 (fuera del rango 0–100)",
      resultado_esperado="HTTP 400 y el nivel de batería guardado no cambia a 250.")
def test_retest_bug005_bateria(sibio, token_admin, registro):
    clave = _lector(sibio, token_admin)
    with registro.paso("El lector envía telemetría con bateria=250") as p:
        r = sibio.llamar("POST", "/api/dispositivos/telemetria", clave_lector=clave,
                         json={"codigo_rfid": "A3:5F:12:9C", "bpm": 72, "contacto": True, "bateria": 250})
        p["observado"] = f"HTTP {r.status_code} {r.datos.get('error') or ''}".strip()
        assert r.status_code == 400, f"BUG-005 sigue abierto: bateria=250 se aceptó (HTTP {r.status_code})"
