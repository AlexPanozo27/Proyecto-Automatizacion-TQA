"""Suite de Seguridad: comprueba con evidencia los controles de seguridad que implementa SIBIO-RFID.
Pruebas no funcionales (seguridad). No modifican SIBIO ni su base: solo leen, o usan cuentas inventadas."""
import base64
import json
import random
import re

from conftest import ADMIN, OPERADOR, SUPERVISOR, login_admin
from soporte import caso

FUGAS = ("Traceback", 'File "', "psycopg", "sqlite3", "SQLAlchemy", "Werkzeug", "SELECT * FROM", "INSERT INTO")
SENSIBLES = ("password_hash", "secreto", "totp", "plantilla", "embedding", "vector", "api_key_hash")


def _fuga(texto):
    return next((f for f in FUGAS if f in texto), None)


@caso("TC-SEG-01", "Cadena de auditoría con SHA-256 íntegra y bien enlazada", suites=["seguridad"], tipo="no_funcional",
      modulo="Seguridad · Auditoría encadenada",
      objetivo="Verificar la cadena de custodia: cada registro de auditoría lleva el hash del anterior "
               "(HMAC-SHA256) y el sistema confirma que nadie alteró la bitácora.",
      precondiciones="Sesión de administrador (con 2FA).",
      datos="GET /api/auditoria/integridad y los últimos 20 registros de GET /api/auditoria",
      resultado_esperado="ok=true, 0 problemas, ancla 'coincide' y cada registro enlaza con el hash del anterior.")
def test_cadena_integridad(sibio, token_admin, registro):
    with registro.paso("Pedir a SIBIO que verifique toda la cadena (GET /api/auditoria/integridad)") as p:
        r = sibio.llamar("GET", "/api/auditoria/integridad", token_admin)
        d = r.datos
        p["observado"] = (f"HTTP {r.status_code}; algoritmo {d.get('algoritmo')}; {d.get('sellados')} de {d.get('total')} "
                          f"registros sellados; problemas={d.get('total_problemas')}; ancla={(d.get('ancla') or {}).get('estado')}; "
                          f"{d.get('ms')} ms")
        assert r.status_code == 200 and d.get("ok") is True and d.get("total_problemas") == 0, "la cadena de auditoría no está íntegra"
    with registro.paso("Comprobar a mano el enlace: huella_anterior de cada registro = huella del registro previo") as p:
        filas = sibio.llamar("GET", "/api/auditoria?limite=20", token_admin).datos
        filas = sorted([f for f in filas if f.get("huella")], key=lambda f: f["eslabon"])
        rotos = [b["id"] for a, b in zip(filas, filas[1:]) if b["eslabon"] == a["eslabon"] + 1 and b["huella_anterior"] != a["huella"]]
        formato = all(re.fullmatch(r"[0-9a-f]{64}", f["huella"]) for f in filas)
        p["observado"] = (f"{len(filas)} registros revisados; enlaces rotos: {len(rotos)}; huellas de 64 hex (256 bits): {formato}; "
                          f"último eslabón {filas[-1]['eslabon'] if filas else '—'}")
        assert filas and not rotos and formato, f"enlaces rotos en los registros {rotos}"


@caso("TC-SEG-02", "La bitácora de auditoría no se puede borrar ni modificar por la API", suites=["seguridad"],
      tipo="no_funcional", modulo="Seguridad · Auditoría encadenada",
      objetivo="Verificar que no existe ninguna vía en la API para alterar o borrar registros de auditoría.",
      precondiciones="Sesión de administrador.", datos="PUT, PATCH y DELETE sobre /api/auditoria y /api/auditoria/1",
      resultado_esperado="Ninguna petición tiene éxito (HTTP 404 o 405) y la cadena sigue íntegra.")
def test_auditoria_solo_agregar(sibio, token_admin, registro):
    for metodo, ruta in (("DELETE", "/api/auditoria/1"), ("PUT", "/api/auditoria/1"), ("PATCH", "/api/auditoria/1"),
                         ("DELETE", "/api/auditoria")):
        with registro.paso(f"Intentar {metodo} {ruta} como administrador") as p:
            r = sibio.llamar(metodo, ruta, token_admin, json={"detalle": "alterado por QA"})
            p["observado"] = f"HTTP {r.status_code}"
            assert r.status_code in (404, 405), f"{metodo} {ruta} respondió {r.status_code}"
    with registro.paso("Confirmar que la cadena sigue íntegra") as p:
        d = sibio.llamar("GET", "/api/auditoria/integridad", token_admin).datos
        p["observado"] = f"ok={d.get('ok')}; problemas={d.get('total_problemas')}"
        assert d.get("ok") is True


@caso("TC-SEG-03", "Bloqueo por fuerza bruta tras 5 contraseñas incorrectas", suites=["seguridad"], tipo="no_funcional",
      modulo="Seguridad · Autenticación",
      objetivo="Verificar que SIBIO frena un ataque de fuerza bruta bloqueando la cuenta tras varios intentos.",
      precondiciones="SIBIO encendido. Se usa un usuario inventado para no bloquear cuentas reales.",
      datos="Usuario qa_fuerza_NNNN; 6 intentos con contraseñas distintas",
      resultado_esperado="Los intentos restantes bajan de 4 a 0 y luego HTTP 429 'Cuenta bloqueada', "
                         "con el mismo mensaje que para un usuario real (no revela si existe).")
def test_fuerza_bruta(sibio, registro):
    usuario = f"qa_fuerza_{random.randint(1000, 9999)}"
    restantes = []
    with registro.paso(f"Enviar 5 contraseñas incorrectas para '{usuario}'") as p:
        for i in range(5):
            r = sibio.llamar("POST", "/api/auth/login", json={"username": usuario, "password": f"Mala{i}x!"})
            restantes.append(r.datos.get("intentos_restantes") if r.status_code == 401 else f"HTTP {r.status_code}")
        p["observado"] = f"Intentos restantes informados: {restantes}"
        assert r.status_code == 429 or restantes[-1] in (0, "HTTP 429"), "no se bloqueó tras 5 intentos"
    with registro.paso("Sexto intento, ahora con cualquier contraseña: debe seguir bloqueado") as p:
        r = sibio.llamar("POST", "/api/auth/login", json={"username": usuario, "password": "OtraClave1"})
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')} (segundos={r.datos.get('segundos')})"
        assert r.status_code == 429, f"se esperaba 429 y llegó {r.status_code}"


@caso("TC-SEG-04", "Verificación en dos pasos (2FA) obligatoria para el administrador", suites=["seguridad"],
      tipo="no_funcional", modulo="Seguridad · Autenticación",
      objetivo="Verificar que la contraseña sola no basta para entrar como administrador y que un código 2FA falso se rechaza.",
      precondiciones=f"Administrador de pruebas ({ADMIN[0]}) con app autenticadora vinculada.",
      datos="Contraseña correcta del administrador; código 2FA falso 000000",
      resultado_esperado="El login devuelve requiere_2fa sin token, y el código falso se rechaza (sin token).")
def test_2fa_obligatoria(sibio, registro):
    with registro.paso("Login del administrador con la contraseña correcta") as p:
        r = sibio.llamar("POST", "/api/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
        p["observado"] = f"HTTP {r.status_code}; requiere_2fa={r.datos.get('requiere_2fa')}; token entregado: {'token' in r.datos}"
        assert r.datos.get("requiere_2fa") is True and "token" not in r.datos, "la contraseña sola dio acceso de administrador"
    with registro.paso("Enviar un código 2FA falso (000000)") as p:
        r = sibio.llamar("POST", "/api/auth/2fa/verificar", json={"desafio": r.datos["desafio"], "codigo": "000000"})
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')}; token entregado: {'token' in r.datos}"
        assert r.status_code >= 400 and "token" not in r.datos, "un código 2FA falso dio acceso"


@caso("TC-SEG-05", "Inyección SQL en el buscador y en el login no tiene efecto", suites=["seguridad"], tipo="no_funcional",
      modulo="Seguridad · Entradas",
      objetivo="Verificar que las consultas usan parámetros y que una inyección SQL clásica no devuelve datos ni rompe el servidor.",
      precondiciones=f"Operador de pruebas ({OPERADOR[0]}).",
      datos="q=\"' OR 1=1 --\", q=\"'; DROP TABLE reclusos; --\" y usuario \"admin' --\"",
      resultado_esperado="El buscador devuelve 0 resultados (no la lista completa), sin HTTP 500; el login con inyección no entra.")
def test_inyeccion_sql(sibio, registro):
    ope = sibio.login(*OPERADOR)
    with registro.paso("Contar los reclusos visibles con una búsqueda normal (sin filtro)") as p:
        total = len(sibio.llamar("GET", "/api/reclusos", ope).datos)
        p["observado"] = f"{total} reclusos visibles"
    for carga in ("' OR 1=1 --", "'; DROP TABLE reclusos; --"):
        with registro.paso(f"Buscar \"{carga}\" (GET /api/reclusos?q=…)") as p:
            r = sibio.llamar("GET", "/api/reclusos", ope, params={"q": carga})
            n = len(r.datos) if isinstance(r.datos, list) else None
            p["observado"] = f"HTTP {r.status_code}; resultados: {n}; fuga de error interno: {_fuga(r.text) or 'no'}"
            assert r.status_code < 500 and not _fuga(r.text), "la inyección provocó un error interno"
            assert n is None or n < total or total == 0, "la inyección devolvió la lista completa"
    with registro.paso("La tabla sigue existiendo: la búsqueda normal devuelve lo mismo que antes") as p:
        despues = len(sibio.llamar("GET", "/api/reclusos", ope).datos)
        p["observado"] = f"{despues} reclusos visibles (antes {total})"
        assert despues == total
    with registro.paso("Login con usuario \"admin' --\" y contraseña cualquiera") as p:
        r = sibio.llamar("POST", "/api/auth/login", json={"username": "admin' --", "password": "x"})
        p["observado"] = f"HTTP {r.status_code}; token entregado: {'token' in r.datos}"
        assert r.status_code in (401, 429) and "token" not in r.datos


@caso("TC-SEG-06", "Al cerrar sesión el token deja de servir aunque alguien lo haya copiado", suites=["seguridad"],
      tipo="no_funcional", modulo="Seguridad · Sesiones",
      objetivo="Verificar que el token JWT se invalida en el servidor al cerrar sesión (no solo en el navegador).",
      precondiciones=f"Operador de pruebas ({OPERADOR[0]}).", datos="Token del operador antes y después de POST /api/auth/salir",
      resultado_esperado="Antes de salir: HTTP 200. Después de salir, el mismo token: HTTP 401 (sesión cerrada).")
def test_sesion_cerrada(sibio, registro):
    tok = sibio.login(*OPERADOR)
    with registro.paso("Usar el token del operador (GET /api/reclusos)") as p:
        r = sibio.llamar("GET", "/api/reclusos", tok)
        p["observado"] = f"HTTP {r.status_code}"
        assert r.status_code == 200
    with registro.paso("Cerrar sesión (POST /api/auth/salir)") as p:
        r = sibio.llamar("POST", "/api/auth/salir", tok)
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('mensaje') or r.datos.get('error')}"
        assert r.status_code == 200
    with registro.paso("Reusar el mismo token copiado") as p:
        r = sibio.llamar("GET", "/api/reclusos", tok)
        p["observado"] = f"HTTP {r.status_code}: {r.datos.get('error')} (código {r.datos.get('codigo')})"
        assert r.status_code == 401, "el token siguió funcionando después de cerrar sesión"


@caso("TC-SEG-07", "La API no expone contraseñas, secretos 2FA ni plantillas biométricas", suites=["seguridad"],
      tipo="no_funcional", modulo="Seguridad · Datos sensibles",
      objetivo="Verificar que las respuestas de la API no devuelven datos sensibles en texto plano.",
      precondiciones="Sesión de administrador y de operador.",
      datos="GET /api/usuarios, /api/reclusos y la ficha de un recluso",
      resultado_esperado="Ningún campo de contraseña, secreto 2FA o plantilla biométrica; la biometría solo aparece "
                         "como 'tiene_rostro' / 'tiene_huella' (sí/no).")
def test_datos_sensibles(sibio, token_admin, registro):
    ope = sibio.login(*OPERADOR)
    lista = sibio.llamar("GET", "/api/reclusos", ope).datos
    for nombre, r in (("GET /api/usuarios (administrador)", sibio.llamar("GET", "/api/usuarios", token_admin)),
                      ("GET /api/reclusos (operador)", sibio.llamar("GET", "/api/reclusos", ope)),
                      (f"GET /api/reclusos/{lista[0]['id']} (ficha)", sibio.llamar("GET", f"/api/reclusos/{lista[0]['id']}", ope))):
        with registro.paso(f"Revisar {nombre}") as p:
            texto = r.text
            hallados = [s for s in SENSIBLES if s in texto]
            hashes = re.findall(r"(pbkdf2:|scrypt:|\$2[aby]\$)", texto)
            blobs = re.findall(r'"[A-Za-z0-9+/=]{400,}"', texto)
            p["observado"] = (f"HTTP {r.status_code}; campos sensibles: {hallados or 'ninguno'}; hashes de contraseña: "
                              f"{len(hashes)}; bloques binarios largos: {len(blobs)}")
            assert r.status_code == 200 and not hallados and not hashes and not blobs


@caso("TC-SEG-08", "Los errores no revelan detalles internos del servidor", suites=["seguridad"], tipo="no_funcional",
      modulo="Seguridad · Manejo de errores",
      objetivo="Verificar que ante datos malformados SIBIO no muestra trazas, consultas SQL ni rutas internas.",
      precondiciones="SIBIO encendido; sesión de administrador.",
      datos="JSON roto en el login, id inexistente, id no numérico y un recluso con tipos de dato inválidos",
      resultado_esperado="Ninguna respuesta contiene Traceback, SQL ni nombres de librerías. Si alguna da HTTP 500, se anota "
                         "como defecto, pero sin filtrar información.")
def test_errores_sin_fugas(sibio, token_admin, registro):
    pruebas = [("Login con JSON roto", "POST", "/api/auth/login", {"data": "{roto", "headers": {"Content-Type": "application/json"}}),
               ("Recluso inexistente", "GET", "/api/reclusos/999999999", {}),
               ("Id no numérico", "GET", "/api/reclusos/abc", {}),
               ("Recluso con tipos inválidos", "POST", "/api/reclusos", {"json": {"nombres": 123, "apellidos": [], "fecha_ingreso": "ayer"}})]
    con500 = []
    for nombre, metodo, ruta, kw in pruebas:
        with registro.paso(f"{nombre}: {metodo} {ruta}") as p:
            r = sibio.llamar(metodo, ruta, None if "login" in ruta else token_admin, recinto=1, **kw)
            fuga = _fuga(r.text)
            if r.status_code >= 500:
                con500.append(ruta)
            p["observado"] = f"HTTP {r.status_code}; fuga de detalle interno: {fuga or 'no'}"
            assert not fuga, f"la respuesta filtra detalles internos ({fuga})"
    with registro.paso("Resumen") as p:
        p["observado"] = ("Sin fugas de información. " + (f"Respuestas HTTP 500 (defecto a corregir): {con500}" if con500 else "Ninguna respuesta HTTP 500."))
