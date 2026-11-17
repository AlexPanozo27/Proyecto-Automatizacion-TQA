"""Pruebas funcionales de la API REST de SIBIO-RFID (autenticación, roles, reclusos, manillas RFID, alertas)."""
import random
import time

import pytest

from conftest import ADMIN, OPERADOR, SUPERVISOR, login_admin
from soporte import caso


def _sufijo():
    return time.strftime("%H%M%S") + str(random.randint(10, 99))


@caso("TC-API-01", "Inicio de sesión con credenciales válidas", suites=["smoke", "sanity", "regression"],
      modulo="Autenticación", objetivo="Comprobar que un usuario válido obtiene una sesión (token) y su rol.",
      precondiciones="SIBIO-RFID encendido con datos de demostración.",
      datos=f"Usuario: {ADMIN[0]} / contraseña de demostración",
      resultado_esperado="HTTP 200 (con código 2FA si el administrador lo tiene), token y rol 'administrador'; "
                         "/auth/yo devuelve el mismo usuario.")
def test_login_valido(sibio, registro):
    datos = login_admin(sibio, registro)
    with registro.paso("Comprobar el token y el rol recibidos") as p:
        p["observado"] = f"token de {len(datos.get('token', ''))} caracteres; rol={datos.get('usuario', {}).get('rol')}"
        assert datos.get("token") and datos["usuario"]["rol"] == "administrador"
    token = datos["token"]
    with registro.paso("Consultar GET /api/auth/yo con el token recibido") as p:
        r = sibio.llamar("GET", "/api/auth/yo", token)
        p["observado"] = f"HTTP {r.status_code}; usuario={r.datos.get('username')}"
        assert r.status_code == 200 and r.datos.get("username") == ADMIN[0]


@caso("TC-API-02", "Contraseña incorrecta y usuario inexistente dan el mismo mensaje",
      suites=["sanity", "regression"], modulo="Autenticación",
      objetivo="Verificar que el sistema no revela si un usuario existe (mensaje genérico).",
      precondiciones="SIBIO-RFID encendido.", datos="admin + clave errónea; usuario aleatorio inexistente",
      resultado_esperado="HTTP 401 y el mismo mensaje 'Usuario o contraseña incorrectos' en ambos casos.")
def test_login_invalido(sibio, registro):
    with registro.paso("Iniciar sesión con contraseña incorrecta") as p:
        r1 = sibio.llamar("POST", "/api/auth/login", json={"username": ADMIN[0], "password": "ClaveMala-99"})
        p["observado"] = f"HTTP {r1.status_code}: {r1.datos.get('error')}"
        assert r1.status_code == 401
    with registro.paso("Iniciar sesión con un usuario que no existe") as p:
        r2 = sibio.llamar("POST", "/api/auth/login", json={"username": "qa_no_existe_" + _sufijo(), "password": "x"})
        p["observado"] = f"HTTP {r2.status_code}: {r2.datos.get('error')}"
        assert r2.status_code == 401
    with registro.paso("Comparar ambos mensajes") as p:
        p["observado"] = "mensajes iguales" if r1.datos.get("error") == r2.datos.get("error") else "mensajes distintos"
        assert r1.datos.get("error") == r2.datos.get("error")
    sibio.login(*ADMIN)   # limpia el contador de intentos fallidos del administrador


@caso("TC-API-03", "Rutas protegidas rechazan peticiones sin sesión o con token alterado",
      suites=["smoke", "regression"], modulo="Seguridad",
      objetivo="Comprobar que la API no entrega datos sin un token válido.",
      precondiciones="SIBIO-RFID encendido.", datos="Sin cabecera Authorization; token falso",
      resultado_esperado="HTTP 401 en ambos casos.")
def test_sin_token(sibio, registro):
    with registro.paso("GET /api/reclusos sin cabecera Authorization") as p:
        r = sibio.llamar("GET", "/api/reclusos")
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')}"
        assert r.status_code == 401
    with registro.paso("GET /api/reclusos con un token alterado") as p:
        r = sibio.llamar("GET", "/api/reclusos", "eyJhbGciOiJIUzI1NiJ9.falso.firma")
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')}"
        assert r.status_code == 401


@caso("TC-API-04", "Permisos por rol: operador y supervisor no acceden a la gestión",
      suites=["regression", "sanity"], modulo="Usuarios y roles",
      objetivo="Verificar el control de acceso basado en roles (RBAC).",
      precondiciones="Usuarios de demostración operador y supervisor activos.",
      datos=f"Operador: {OPERADOR[0]}; Supervisor: {SUPERVISOR[0]}",
      resultado_esperado="HTTP 403 para operador en /usuarios y supervisor en /auditoria; 200 para el administrador.")
def test_permisos_por_rol(sibio, token_admin, registro):
    ope, sup = sibio.login(*OPERADOR), sibio.login(*SUPERVISOR)
    with registro.paso("Operador intenta listar usuarios (GET /api/usuarios)") as p:
        r = sibio.llamar("GET", "/api/usuarios", ope)
        p["observado"] = f"HTTP {r.status_code}"
        assert r.status_code == 403
    with registro.paso("Supervisor intenta abrir la auditoría (GET /api/auditoria)") as p:
        r = sibio.llamar("GET", "/api/auditoria", sup)
        p["observado"] = f"HTTP {r.status_code}"
        assert r.status_code == 403
    with registro.paso("Administrador lista usuarios y no se expone ningún hash de contraseña") as p:
        r = sibio.llamar("GET", "/api/usuarios", token_admin)
        p["observado"] = f"HTTP {r.status_code}; {len(r.datos)} usuarios; password_hash expuesto: {'password_hash' in r.text}"
        assert r.status_code == 200 and "password_hash" not in r.text


@caso("TC-API-05", "Registrar un recluso y encontrarlo en la búsqueda", suites=["regression", "integration"],
      modulo="Reclusos", objetivo="Comprobar el alta de un recluso y que la búsqueda lo encuentra por nombre.",
      precondiciones="Sesión de administrador; penal San Pedro (id 1).",
      datos="Código QA-xxxx, nombres 'Prueba Automatizada', apellidos 'Qa Sibio'",
      resultado_esperado="HTTP 201 al registrar; la búsqueda devuelve el código registrado.")
def test_registrar_y_buscar_recluso(sibio, token_admin, registro):
    codigo = "QA-" + _sufijo()
    with registro.paso(f"POST /api/reclusos con código {codigo}") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": codigo, "nombres": "Prueba Automatizada", "apellidos": "Qa Sibio",
                               "pabellon": "A", "situacion": "preventivo"})
        p["observado"] = f"HTTP {r.status_code}; id={r.datos.get('id')} {r.datos.get('error') or ''}"
        assert r.status_code == 201, f"se esperaba 201 y llegó {r.status_code}"
    with registro.paso(f"Buscar '{codigo}' en GET /api/reclusos?q=") as p:
        r = sibio.llamar("GET", f"/api/reclusos?q={codigo}", token_admin, recinto=1)
        lista = r.datos if isinstance(r.datos, list) else r.datos.get("reclusos", r.datos.get("items", []))
        codigos = [x.get("codigo_interno") for x in lista]
        p["observado"] = f"HTTP {r.status_code}; resultados: {codigos[:5]}"
        assert codigo in codigos


@caso("TC-API-06", "Código interno duplicado y campos obligatorios vacíos son rechazados",
      suites=["regression"], modulo="Reclusos",
      objetivo="Validar las reglas de negocio al registrar reclusos.",
      precondiciones="Existe el recluso SP-0412 (datos de demostración).",
      datos="codigo_interno=SP-0412; registro sin nombres",
      resultado_esperado="HTTP 409 por duplicado y HTTP 400 por campo vacío.")
def test_validaciones_recluso(sibio, token_admin, registro):
    with registro.paso("Registrar un recluso con el código ya existente SP-0412") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": "SP-0412", "nombres": "Otro", "apellidos": "Recluso"})
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')}"
        assert r.status_code == 409
    with registro.paso("Registrar un recluso sin nombres") as p:
        r = sibio.llamar("POST", "/api/reclusos", token_admin, recinto=1,
                         json={"codigo_interno": "QA-" + _sufijo(), "nombres": "", "apellidos": "Sin Nombre"})
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')}"
        assert r.status_code == 400


@caso("TC-API-07", "Lectura RFID simulada en zona restringida genera alerta crítica",
      suites=["integration", "regression", "smoke"], modulo="Manillas RFID y Alertas",
      objetivo="Comprobar la integración lector RFID → evento → alerta (sin hardware, lector simulado por API).",
      precondiciones="Zona 'Muro perimetral norte' (restringida, id 7); manilla A3:5F:12:9C asignada a SP-0412.",
      datos="Lector QA creado por la prueba; codigo_rfid=A3:5F:12:9C",
      resultado_esperado="La lectura reconoce al recluso y aparece una alerta crítica de zona restringida.")
def test_rfid_zona_restringida(sibio, token_admin, registro):
    with registro.paso("Crear un lector simulado en la zona restringida (POST /api/puntos-control)") as p:
        r = sibio.llamar("POST", "/api/puntos-control", token_admin, recinto=1,
                         json={"nombre": "Lector QA " + _sufijo(), "tipo": "interno", "zona_id": 7})
        p["observado"] = f"HTTP {r.status_code}; punto id={r.datos.get('id')}"
        assert r.status_code in (200, 201) and r.datos.get("api_key")
    clave = r.datos["api_key"]
    with registro.paso("El lector envía la lectura de la manilla A3:5F:12:9C") as p:
        r = sibio.llamar("POST", "/api/dispositivos/lectura-rfid", clave_lector=clave, json={"codigo_rfid": "A3:5F:12:9C"})
        p["observado"] = f"HTTP {r.status_code}; reconocido={r.datos.get('reconocido')}; zona={r.datos.get('zona')}"
        assert r.status_code == 200 and r.datos.get("reconocido") is True
    with registro.paso("Buscar la alerta crítica de zona restringida en GET /api/alertas") as p:
        r = sibio.llamar("GET", "/api/alertas?estado=pendiente", token_admin)
        criticas = [a for a in r.datos if a.get("severidad") == "critica" and "restringida" in (a.get("descripcion") or "")]
        p["observado"] = f"HTTP {r.status_code}; {len(criticas)} alerta(s) crítica(s) de zona restringida"
        assert criticas, "no se generó la alerta de zona restringida"


@caso("TC-API-08", "Manilla desconocida es rechazada y queda como posible suplantación",
      suites=["integration", "regression"], modulo="Manillas RFID",
      objetivo="Verificar que una manilla no registrada no se acepta.",
      precondiciones="Existe al menos un lector; FF:FF:FF:FF no está registrada.",
      datos="codigo_rfid=FF:FF:FF:FF",
      resultado_esperado="HTTP 404 'Manilla no válida' y alerta de posible suplantación.")
def test_rfid_desconocida(sibio, token_admin, registro):
    r = sibio.llamar("POST", "/api/puntos-control", token_admin, recinto=1,
                     json={"nombre": "Lector QA " + _sufijo(), "tipo": "interno", "zona_id": 1})
    clave = r.datos.get("api_key")
    with registro.paso("El lector envía la manilla desconocida FF:FF:FF:FF") as p:
        r = sibio.llamar("POST", "/api/dispositivos/lectura-rfid", clave_lector=clave, json={"codigo_rfid": "FF:FF:FF:FF"})
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('mensaje')}"
        assert r.status_code == 404 and r.datos.get("reconocido") is False
    with registro.paso("Comprobar la alerta de posible suplantación") as p:
        r = sibio.llamar("GET", "/api/alertas?estado=pendiente", token_admin)
        hay = [a for a in r.datos if "FF:FF:FF:FF" in (a.get("descripcion") or "")]
        p["observado"] = f"{len(hay)} alerta(s) que mencionan FF:FF:FF:FF"
        assert hay


@caso("TC-API-09", "Centro de monitoreo entrega los indicadores (KPI)", suites=["smoke", "sanity", "regression"],
      modulo="Centro de monitoreo", objetivo="Comprobar que el tablero devuelve los KPI principales.",
      precondiciones="Sesión de administrador.", datos="GET /api/dashboard",
      resultado_esperado="HTTP 200 con los KPI de reclusos, manillas, eventos y alertas.")
def test_dashboard(sibio, token_admin, registro):
    with registro.paso("Consultar GET /api/dashboard") as p:
        r = sibio.llamar("GET", "/api/dashboard", token_admin)
        kpi = r.datos.get("kpi", {})
        p["observado"] = f"HTTP {r.status_code} en {r.ms} ms; KPI: {kpi}"
        assert r.status_code == 200 and kpi, "el tablero no trajo KPI"
    with registro.paso("Comprobar que los KPI son números no negativos") as p:
        malos = [k for k, v in kpi.items() if isinstance(v, (int, float)) and v < 0]
        p["observado"] = "todos válidos" if not malos else f"negativos: {malos}"
        assert not malos


@caso("TC-API-10", "Huella dactilar con sensor R307 real", suites=["regression", "integration"],
      modulo="Biometría (huella)", objetivo="Verificar la captura con el sensor físico R307.",
      precondiciones="Sensor R307 conectado (HUELLA_MODO=r307). Fuera del alcance: no se prueba hardware.",
      datos="GET /api/huella/estado",
      resultado_esperado="Se omite (SKIPPED) si el sensor no está conectado.")
def test_huella_real(sibio, token_admin, registro):
    with registro.paso("Consultar el estado del lector de huella") as p:
        r = sibio.llamar("GET", "/api/huella/estado", token_admin)
        p["observado"] = f"modo={r.datos.get('modo')}: {r.datos.get('mensaje')}"
    if r.datos.get("modo") != "r307":
        pytest.skip(f"Sensor de huella no conectado (modo {r.datos.get('modo')}). El hardware está fuera del alcance de estas pruebas.")
    assert r.datos.get("estado") == "conectado"
