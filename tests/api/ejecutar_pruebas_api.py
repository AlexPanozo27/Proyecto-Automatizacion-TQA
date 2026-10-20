"""Ejecuta los casos de prueba funcionales contra la API de SIBIO-RFID y guarda resultados + logs."""
import base64, json, os, sqlite3, time, datetime as dt
import requests

B = os.environ.get("SIBIO_API", "http://localhost:5000/api")
DB = os.environ.get("SIBIO_DB", "instance/sibio.db")
OUT = os.environ.get("SIBIO_OUT", "reportes/resultados")
SEL = {"TC-001","TC-002","TC-004","TC-010","TC-012","TC-013","TC-016","TC-018","TC-021","TC-024","TC-026","TC-029","TC-030","TC-031"}
os.makedirs(OUT, exist_ok=True)

LOG = []
def call(m, path, tok=None, key=None, **kw):
    h = {}
    if tok: h["Authorization"] = f"Bearer {tok}"
    if key: h["X-API-Key"] = key
    t0 = time.time()
    r = requests.request(m, B + path, headers=h, timeout=20, **kw)
    ms = round((time.time() - t0) * 1000)
    try: body = r.json()
    except Exception: body = r.text[:300]
    s = json.dumps(body, ensure_ascii=False)
    LOG.append(f"{m} {path} {json.dumps(kw.get('json'), ensure_ascii=False) if kw.get('json') is not None else ''}\n  -> HTTP {r.status_code} ({ms} ms) {s[:400]}")
    return r.status_code, body

def login(u, p):
    c, b = call("POST", "/auth/login", json={"username": u, "password": p})
    return b.get("token") if c == 200 else None

IMG = "data:image/jpeg;base64," + base64.b64encode(os.urandom(3000)).decode()
def img(): return "data:image/jpeg;base64," + base64.b64encode(os.urandom(3000)).decode()

R = {}
def tc(id_):
    def deco(fn):
        if id_ not in SEL:
            return fn
        LOG.clear()
        pasos = []
        def p(accion, obs, ok):
            pasos.append({"accion": accion, "observado": obs, "estado": "PASS" if ok else "FAIL"})
        try:
            fn(p)
        except Exception as e:
            pasos.append({"accion": "Excepción del script", "observado": repr(e), "estado": "FAIL"})
        R[id_] = {"pasos": pasos, "log": list(LOG), "hora": dt.datetime.now().strftime("%H:%M")}
        with open(f"{OUT}/log_{id_}.txt", "w") as f:
            f.write("\n".join(LOG))
        print(id_, ["PASS" if all(x["estado"] == "PASS" for x in pasos) else "FAIL"], len(pasos))
        return fn
    return deco

ADM = login("admin", "Admin12345")
OPE = login("jperez", "Demo12345")
SUP = login("agutierrez", "Demo12345")
db = lambda: sqlite3.connect(DB)
puntos = {p["nombre"]: p for p in call("GET", "/puntos-control", ADM)[1]}
def api_key(nombre):
    return db().execute("SELECT api_key FROM puntos_control WHERE nombre=?", (nombre,)).fetchone()[0]

# ---------------- Autenticación ----------------
@tc("TC-001")
def _(p):
    c, b = call("POST", "/auth/login", json={"username": "admin", "password": "Admin12345"})
    p("Iniciar sesión con admin / clave válida", f"HTTP {c}; token JWT recibido ({len(b.get('token',''))} car.); rol={b.get('usuario',{}).get('rol')}", c == 200 and b.get("token") and b["usuario"]["rol"] == "administrador")
    c, b = call("GET", "/auth/yo", b.get("token"))
    p("Consultar /auth/yo con el token", f"HTTP {c}; username={b.get('username')}", c == 200 and b.get("username") == "admin")

@tc("TC-002")
def _(p):
    c, b = call("POST", "/auth/login", json={"username": "admin", "password": "ClaveMala99"})
    p("Iniciar sesión con contraseña incorrecta", f"HTTP {c}; mensaje: {b.get('error')}", c == 401 and "incorrectos" in b.get("error", ""))
    c, b = call("POST", "/auth/login", json={"username": "noexiste", "password": "Admin12345"})
    p("Iniciar sesión con usuario inexistente", f"HTTP {c}; mensaje: {b.get('error')} (mismo mensaje, no revela si el usuario existe)", c == 401 and "incorrectos" in b.get("error", ""))
    c, b = call("POST", "/auth/login", json={})
    p("Iniciar sesión con campos vacíos", f"HTTP {c}; mensaje: {b.get('error')}", c == 401)
    n = db().execute("SELECT COUNT(*) FROM auditoria WHERE accion='login_fallido'").fetchone()[0]
    p("Revisar auditoría de intentos fallidos", f"{n} registros 'login_fallido' en auditoría", n >= 3)

@tc("TC-003")
def _(p):
    c, b = call("GET", "/reclusos")
    p("GET /reclusos sin cabecera Authorization", f"HTTP {c}; {b.get('error')}", c == 401)
    c, b = call("GET", "/reclusos", "eyJhbGciOiJIUzI1NiJ9.falso.firma")
    p("GET /reclusos con token alterado", f"HTTP {c}; {b.get('error')}", c == 401)
    import jwt
    vencido = jwt.encode({"sub": "1", "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)}, os.environ["JWT_SECRET"], algorithm="HS256")
    c, b = call("GET", "/reclusos", vencido)
    p("GET /reclusos con token vencido (exp - 1 min)", f"HTTP {c}; {b.get('error')}", c == 401 and "expirada" in b.get("error", ""))

@tc("TC-004")
def _(p):
    c, b = call("GET", "/usuarios", OPE)
    p("Operador (jperez) lista usuarios", f"HTTP {c}; {b.get('error') if isinstance(b, dict) else ''}", c == 403)
    c, b = call("GET", "/auditoria", SUP)
    p("Supervisor (agutierrez) abre auditoría", f"HTTP {c}; {b.get('error') if isinstance(b, dict) else ''}", c == 403)
    c, b = call("POST", "/reclusos", SUP, json={"codigo_interno": "SP-9001", "nombres": "X", "apellidos": "Y"})
    p("Supervisor intenta registrar un recluso", f"HTTP {c}; {b.get('error')}", c == 403)
    c, b = call("GET", "/usuarios", ADM)
    p("Administrador lista usuarios", f"HTTP {c}; {len(b)} usuarios; ¿algún password_hash expuesto? {'password_hash' in json.dumps(b)}", c == 200 and "password_hash" not in json.dumps(b))

# ---------------- Usuarios ----------------
@tc("TC-005")
def _(p):
    d = {"nombre_completo": "Sgto. Pedro Rojas", "grado": "Sargento", "username": "projas", "password": "Inicial2026", "rol": "operador"}
    c, b = call("POST", "/usuarios", ADM, json=d)
    p("Crear usuario operador con datos válidos", f"HTTP {c}; {b.get('mensaje')}", c == 201)
    c, b = call("POST", "/auth/login", json={"username": "projas", "password": "Inicial2026"})
    p("Ingresar con el usuario nuevo", f"HTTP {c}; rol={b.get('usuario',{}).get('rol')}; debe_cambiar_clave={b.get('usuario',{}).get('debe_cambiar_clave')}", c == 200 and b["usuario"]["debe_cambiar_clave"] is True)
    t = b.get("token")
    c, b = call("POST", "/auth/cambiar-clave", t, json={"actual": "Inicial2026", "nueva": "Rojas2026Seg"})
    p("Cambiar la contraseña temporal", f"HTTP {c}; {b}", c == 200)
    c, b = call("POST", "/usuarios", ADM, json=d)
    p("Repetir el alta con el mismo username", f"HTTP {c}; {b.get('error')}", c == 409)

@tc("TC-006")
def _(p):
    base = {"nombre_completo": "Prueba Límite", "rol": "operador"}
    c, b = call("POST", "/usuarios", ADM, json={**base, "username": "lim7", "password": "Abc1234"})
    p("Contraseña de 7 caracteres (límite inferior - 1)", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", "/usuarios", ADM, json={**base, "username": "lim8", "password": "Abcd1234"})
    p("Contraseña de 8 caracteres (límite inferior)", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 201)
    c, b = call("POST", "/usuarios", ADM, json={**base, "username": "rolx", "password": "Abcd1234", "rol": "jefe"})
    p("Rol inexistente 'jefe'", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", "/usuarios", ADM, json={"username": "faltan"})
    p("Campos obligatorios vacíos", f"HTTP {c}; {b.get('error')}", c == 400)

@tc("TC-007")
def _(p):
    base = {"nombre_completo": "Prueba Política", "rol": "operador"}
    c, b = call("POST", "/usuarios", ADM, json={**base, "username": "solonum", "password": "11111111"})
    p("Crear usuario con contraseña solo numérica '11111111'", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 400)
    c, b = call("POST", "/usuarios", ADM, json={**base, "username": "facil", "password": "Demo12345"})
    p("Crear usuario con la contraseña de la lista prohibida 'Demo12345'", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 400)
    t = login("lim8", "Abcd1234")
    c, b = call("POST", "/auth/cambiar-clave", t, json={"actual": "Abcd1234", "nueva": "22222222"})
    p("Comparación: cambiar clave a '22222222' desde 'Mi cuenta'", f"HTTP {c}; {b.get('error')}", c == 400)

@tc("TC-008")
def _(p):
    uid = db().execute("SELECT id FROM usuarios WHERE username='projas'").fetchone()[0]
    c, b = call("PATCH", f"/usuarios/{uid}/estado", ADM, json={"activo": False})
    p("Desactivar al usuario projas", f"HTTP {c}; {b.get('mensaje')}", c == 200)
    c, b = call("POST", "/auth/login", json={"username": "projas", "password": "Rojas2026Seg"})
    p("projas intenta iniciar sesión", f"HTTP {c}; {b.get('error')}", c == 403)
    c, b = call("PATCH", "/usuarios/1/estado", ADM, json={"activo": False})
    p("Admin intenta desactivarse a sí mismo", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("PATCH", f"/usuarios/{uid}/estado", ADM, json={"activo": True})
    p("Reactivar a projas", f"HTTP {c}; {b.get('mensaje')}", c == 200 and login("projas", "Rojas2026Seg"))

@tc("TC-009")
def _(p):
    c, b = call("POST", "/usuarios", ADM, json={"nombre_completo": "Duplicado", "username": "JPerez", "password": "Abcd12345", "rol": "operador"})
    p("Crear usuario 'JPerez' cuando ya existe 'jperez'", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 409)
    n = db().execute("SELECT COUNT(*) FROM usuarios WHERE LOWER(username)='jperez'").fetchone()[0]
    p("Contar cuentas con username jperez (sin distinguir mayúsculas)", f"{n} cuentas", n == 1)

# ---------------- Reclusos ----------------
@tc("TC-010")
def _(p):
    d = {"codigo_interno": "SP-0500", "ci": "7845123 LP", "nombres": "Ramiro", "apellidos": "Huanca Quispe", "pabellon": "A", "celda": "A-20", "situacion": "preventivo"}
    c, b = call("POST", "/reclusos", OPE, json=d)
    p("Registrar recluso con datos válidos (operador)", f"HTTP {c}; id={b.get('id')}", c == 201)
    c, b = call("GET", "/reclusos?q=huanca q", OPE)
    c, b = call("GET", "/reclusos?q=ramiro", OPE)
    p("Buscar 'ramiro'", f"HTTP {c}; {len(b)} resultado(s): {[x['codigo_interno'] for x in b]}", c == 200 and any(x["codigo_interno"] == "SP-0500" for x in b))
    c, b = call("GET", "/reclusos?q=7845123", OPE)
    p("Buscar por CI '7845123'", f"HTTP {c}; {len(b)} resultado(s)", c == 200 and len(b) == 1)

@tc("TC-011")
def _(p):
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0500", "nombres": "Otro", "apellidos": "Recluso"})
    p("Registrar con código interno ya existente SP-0500", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0501", "nombres": "", "apellidos": "Sin Nombre"})
    p("Registrar sin nombres", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", "/reclusos", OPE, json={"nombres": "A", "apellidos": "B"})
    p("Registrar sin código interno", f"HTTP {c}; {b.get('error')}", c == 400)

@tc("TC-012")
def _(p):
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0502", "ci": "ABCDEFG", "nombres": "Prueba", "apellidos": "Ci Letras"})
    p("Registrar recluso con CI = 'ABCDEFG'", f"HTTP {c}; {b.get('error') or 'registrado id=' + str(b.get('id'))}", c == 400)
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0503", "ci": "@@##!!", "nombres": "Prueba", "apellidos": "Ci Simbolos"})
    p("Registrar recluso con CI = '@@##!!'", f"HTTP {c}; {b.get('error') or 'registrado id=' + str(b.get('id'))}", c == 400)
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0504", "ci": "4567890 LP", "nombres": "Prueba", "apellidos": "Ci Valido"})
    p("Registrar recluso con CI válido '4567890 LP'", f"HTTP {c}; id={b.get('id')}", c == 201)

@tc("TC-013")
def _(p):
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0505", "nombres": "Prueba", "apellidos": "Estado Raro", "estado": "fugado"})
    p("Registrar recluso con estado 'fugado'", f"HTTP {c}; {b.get('error') or 'registrado id=' + str(b.get('id'))}", c == 400)
    rid = b.get("id")
    c, b = call("PUT", f"/reclusos/{rid or 1}", OPE, json={"estado": "fugado"})
    p("Comparación: editar un recluso a estado 'fugado'", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0506", "nombres": "Prueba", "apellidos": "Situacion Rara", "situacion": "xyz"})
    p("Registrar recluso con situación 'xyz'", f"HTTP {c}; {b.get('error') or 'registrado id=' + str(b.get('id'))}", c == 400)
    c, b = call("POST", "/reclusos", OPE, json={"codigo_interno": "SP-0507", "nombres": "Prueba", "apellidos": "Nace Futuro", "fecha_nacimiento": "2090-01-01"})
    p("Registrar recluso con fecha de nacimiento 2090-01-01", f"HTTP {c}; {b.get('error') or 'registrado id=' + str(b.get('id'))}", c == 400)
    c, b = call("GET", "/dashboard", ADM)
    p("Revisar KPI 'reclusos activos' del Inicio", f"KPI reclusos = {b['kpi']['reclusos']} (el recluso 'fugado' no se cuenta como activo ni como liberado)", True)

@tc("TC-014")
def _(p):
    rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0504'").fetchone()[0]
    c, b = call("PUT", f"/reclusos/{rid}", OPE, json={"codigo_interno": "SP-0412"})
    p("Editar SP-0504 y poner el código interno SP-0412 (ya usado)", f"HTTP {c}; {str(b)[:150]}", c == 409)
    c, b = call("PUT", f"/reclusos/{rid}", OPE, json={"celda": "A-21", "motivo_cambio": "Reubicación"})
    p("Editar la celda con un valor válido", f"HTTP {c}; {b.get('mensaje')}", c == 200)
    c, b = call("GET", f"/reclusos/{rid}/historial", OPE)
    mov = [x for x in b if x.get("categoria") == "movimiento"]
    p("Ver historial de movimientos", f"HTTP {c}; movimientos: {[(x['titulo'], x['detalle']) for x in mov]}", c == 200 and any("A-21" in x["detalle"] for x in mov))

@tc("TC-015")
def _(p):
    c, b = call("PUT", "/reclusos/1", OPE, json={"estado": "liberado", "motivo_cambio": "Orden judicial"})
    p("Cambiar estado de Carlos Quispe (SP-0412) a 'liberado'", f"HTTP {c}; {b.get('mensaje')}", c == 200 and "retiró la manilla" in b.get("mensaje", ""))
    m = db().execute("SELECT estado, recluso_id FROM manillas WHERE codigo_rfid='A3:5F:12:9C'").fetchone()
    p("Verificar estado de la manilla A3:5F:12:9C", f"estado={m[0]}, recluso_id={m[1]}", m == ("disponible", None))
    c, b = call("PUT", "/reclusos/1", OPE, json={"estado": "activo"})
    p("Restaurar a 'activo' para las siguientes pruebas", f"HTTP {c}", c == 200)
    mid = db().execute("SELECT id FROM manillas WHERE codigo_rfid='A3:5F:12:9C'").fetchone()[0]
    c, b = call("POST", f"/manillas/{mid}/asignar", OPE, json={"recluso_id": 1})
    p("Volver a asignar su manilla", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 200)

# ---------------- Biometría ----------------
@tc("TC-016")
def _(p):
    rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0500'").fetchone()[0]
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": [img(), img(), img()]})
    p("Registrar rostro con 3 fotos", f"HTTP {c}; {b.get('mensaje')} (motor {b.get('motor')})", c == 200)
    c, b = call("POST", f"/reclusos/{rid}/biometria/huella", OPE, json={"lecturas": 3})
    p("Registrar huella (3 lecturas)", f"HTTP {c}; {b.get('mensaje')}; plantilla {b.get('bytes_plantilla')} bytes", c == 200)
    c, b = call("GET", f"/reclusos/{rid}", OPE)
    p("Ver ficha del recluso", f"tiene_rostro={b.get('tiene_rostro')}, tiene_huella={b.get('tiene_huella')}, tiene_foto={b.get('tiene_foto')}", b.get("tiene_rostro") == 1 and b.get("tiene_huella") == 1)
    blob = db().execute("SELECT embedding_facial FROM perfiles_biometricos WHERE recluso_id=?", (rid,)).fetchone()[0]
    legible = blob[:1] in (b"[", b"{")
    p("Leer el embedding directo en la base de datos", f"{len(blob)} bytes; primeros bytes {blob[:8].hex()} ; ¿texto JSON legible? {legible}", not legible)

@tc("TC-017")
def _(p):
    rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0500'").fetchone()[0]
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": []})
    p("Registrar rostro con 0 fotos", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": [img()]})
    p("Registrar rostro con 1 foto (límite inferior)", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 200)
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": [img() for _ in range(5)]})
    p("Registrar rostro con 5 fotos (límite superior)", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 200)
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": [img() for _ in range(6)]})
    p("Registrar rostro con 6 fotos (límite superior + 1)", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", f"/reclusos/{rid}/biometria/rostro", OPE, json={"imagenes": ["data:image/jpeg;base64,@@noesbase64"]})
    p("Registrar rostro con imagen mal codificada", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", "/reclusos/99999/biometria/rostro", OPE, json={"imagenes": [img()]})
    p("Registrar rostro a recluso inexistente (id 99999)", f"HTTP {c}; {b.get('error')}", c == 404)

# ---------------- Verificación ----------------
PV = None
def iniciar(uid="7B:21:C4:0E", tipo="visita"):
    return call("POST", "/verificacion/iniciar", OPE, json={"codigo_rfid": uid, "tipo": tipo, "punto_control_id": puntos["Puerta de visitas"]["id"]})

@tc("TC-018")
def _(p):
    t0 = time.time()
    c, b = iniciar()
    vid = b.get("verificacion_id")
    p("Paso 1 RFID: iniciar con manilla 7B:21:C4:0E (Luis Condori) en Puerta de visitas", f"HTTP {c}; verificación {vid}; recluso {b.get('recluso',{}).get('nombres')} {b.get('recluso',{}).get('apellidos')}; siguiente={b.get('siguiente')}", c == 201)
    c, b = call("POST", f"/verificacion/{vid}/rostro", OPE, json={"imagen": img()})
    p("Paso 2 Rostro: enviar foto", f"HTTP {c}; ok={b.get('ok')}; similitud={b.get('similitud')}", c == 200 and b.get("ok"))
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(5)]})
    p("Paso 3 Prueba de vida: 5 cuadros", f"HTTP {c}; ok={b.get('ok')}; {b.get('detalle')}", c == 200 and b.get("ok"))
    c, b = call("POST", f"/verificacion/{vid}/huella", OPE, json={})
    seg = round(time.time() - t0, 2)
    p("Paso 4 Huella", f"HTTP {c}; exitosa={b.get('exitosa')}; puntaje={b.get('puntaje')}; tiempo servidor={b.get('segundos')} s", c == 200 and b.get("exitosa"))
    p("Medir tiempo total de la verificación (RNF-1 < 5 s)", f"{seg} s de extremo a extremo", seg < 5)
    ev = db().execute("SELECT tipo, metodo, resultado FROM eventos_identificacion WHERE id=?", (b.get("evento_id"),)).fetchone()
    p("Revisar evento registrado", f"evento {b.get('evento_id')}: {ev}", ev == ("visita", "multimodal", "exito"))

@tc("TC-019")
def _(p):
    c, b = iniciar()
    vid = b.get("verificacion_id")
    p("Iniciar verificación con manilla de Luis Condori", f"HTTP {c}; verificación {vid}", c == 201)
    c, b = call("POST", f"/verificacion/{vid}/rostro", OPE, json={"imagen": img(), "simular": "no_coincide"})
    p("Presentar un rostro que no coincide", f"HTTP {c}; ok={b.get('ok')}; terminada={b.get('terminada')}; motivo: {b.get('motivo')}", c == 200 and b.get("ok") is False and b.get("terminada"))
    a = db().execute("SELECT tipo, severidad FROM alertas WHERE id=?", (b.get("alerta_id"),)).fetchone()
    p("Revisar alerta generada", f"alerta {b.get('alerta_id')}: {a}", a == ("suplantacion", "critica"))
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(3)]})
    p("Intentar continuar la verificación cerrada", f"HTTP {c}; {b.get('error')}", c == 409)

@tc("TC-020")
def _(p):
    c, b = iniciar()
    vid = b.get("verificacion_id")
    p("Iniciar verificación", f"HTTP {c}; verificación {vid}; siguiente={b.get('siguiente')}", c == 201)
    c, b = call("POST", f"/verificacion/{vid}/huella", OPE, json={})
    p("Saltar directo al paso huella", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(3)]})
    p("Saltar al paso prueba de vida", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("POST", "/verificacion/iniciar", OPE, json={"codigo_rfid": "FF:FF:FF:FF", "tipo": "visita", "punto_control_id": puntos["Puerta de visitas"]["id"]})
    p("Iniciar con manilla no registrada FF:FF:FF:FF", f"HTTP {c}; {b.get('error')}", c == 404)
    c, b = call("POST", "/verificacion/iniciar", OPE, json={"codigo_rfid": "7B:21:C4:0E", "tipo": "paseo", "punto_control_id": puntos["Puerta de visitas"]["id"]})
    p("Iniciar con tipo de control inválido 'paseo'", f"HTTP {c}; {b.get('error')}", c == 400)

@tc("TC-021")
def _(p):
    c, b = iniciar()
    vid = b.get("verificacion_id")
    call("POST", f"/verificacion/{vid}/rostro", OPE, json={"imagen": img()})
    p("Iniciar y aprobar rostro", f"verificación {vid}", c == 201)
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(2)]})
    p("Prueba de vida con 2 cuadros (límite 3 - 1)", f"HTTP {c}; {b.get('error')}", c == 400)
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(3)], "simular": "foto"})
    p("1er intento con foto estática", f"HTTP {c}; ok={b.get('ok')}; reintentar={b.get('reintentar')}; terminada={b.get('terminada')}", c == 200 and b.get("reintentar") and not b.get("terminada"))
    c, b = call("POST", f"/verificacion/{vid}/vida", OPE, json={"frames": [img() for _ in range(3)], "simular": "foto"})
    p("2do intento con foto estática", f"HTTP {c}; terminada={b.get('terminada')}; exitosa={b.get('exitosa')}", c == 200 and b.get("terminada") and b.get("exitosa") is False)
    a = db().execute("SELECT tipo, severidad FROM alertas WHERE id=?", (b.get("alerta_id"),)).fetchone()
    p("Revisar alerta", f"{a}", a == ("intento_foto", "critica"))

@tc("TC-022")
def _(p):
    c, b = iniciar(tipo="egreso")
    p("Iniciar EGRESO de Luis Condori sin salida programada hoy", f"HTTP {c}; advertencias: {b.get('advertencias')}", c == 201 and b.get("advertencias"))
    a = db().execute("SELECT tipo, severidad FROM alertas ORDER BY id DESC LIMIT 1").fetchone()
    p("Revisar última alerta", f"{a}", a == ("salida_no_programada", "alta"))

# ---------------- Manillas ----------------
@tc("TC-023")
def _(p):
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "a1 b2 c3 d4"})
    p("Registrar UID 'a1 b2 c3 d4' (con espacios y minúsculas)", f"HTTP {c}; guardado como {b.get('codigo_rfid')}", c == 201 and b.get("codigo_rfid") == "A1:B2:C3:D4")
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "A1B2C3D4"})
    p("Registrar el mismo UID escrito 'A1B2C3D4'", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("GET", "/manillas/buscar?uid=a1:b2:c3:d4", OPE)
    p("Buscar la manilla por UID", f"HTTP {c}; id={b.get('id')}; estado={b.get('estado')}", c == 200 and b.get("estado") == "disponible")

@tc("TC-024")
def _(p):
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "A35F1"})
    p("UID de 5 dígitos hex 'A35F1'", f"HTTP {c}; {b.get('error') or b.get('codigo_rfid')}", c == 400)
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "B4C5D6"})
    p("UID de 3 bytes 'B4C5D6'", f"HTTP {c}; {b.get('error') or 'registrada como ' + str(b.get('codigo_rfid'))}", c == 400)
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "C1D2E3F"})
    p("UID de 7 dígitos hex (byte incompleto) 'C1D2E3F'", f"HTTP {c}; {b.get('error') or 'registrada como ' + str(b.get('codigo_rfid'))}", c == 400)
    c, b = call("POST", "/manillas", OPE, json={"codigo_rfid": "ZZ-XX-QQ"})
    p("UID sin dígitos hexadecimales 'ZZ-XX-QQ'", f"HTTP {c}; {b.get('error')}", c == 400)

@tc("TC-025")
def _(p):
    mid = db().execute("SELECT id FROM manillas WHERE codigo_rfid='A1:B2:C3:D4'").fetchone()[0]
    rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0500'").fetchone()[0]
    c, b = call("POST", f"/manillas/{mid}/asignar", OPE, json={"recluso_id": rid})
    p("Asignar A1:B2:C3:D4 a Ramiro Huanca (SP-0500)", f"HTTP {c}; {b.get('mensaje') or b.get('error')}", c == 200)
    libre = db().execute("SELECT id FROM manillas WHERE codigo_rfid='E4:6B:02:D9'").fetchone()[0]
    c, b = call("POST", f"/manillas/{libre}/asignar", OPE, json={"recluso_id": rid})
    p("Asignar una segunda manilla al mismo recluso", f"HTTP {c}; {b.get('error')}", c == 409)
    otro = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0452'").fetchone()[0]
    c, b = call("POST", f"/manillas/{mid}/asignar", OPE, json={"recluso_id": otro})
    p("Asignar la manilla ya asignada a otro recluso (SP-0452)", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("POST", f"/manillas/{mid}/asignar", OPE, json={"recluso_id": 99999})
    p("Asignar a recluso inexistente", f"HTTP {c}; {b.get('error')}", c == 404)

# Preparación de TC-026 (precondición): manilla A1:B2:C3:D4 registrada y asignada a SP-0500
_c, _b = call("POST", "/manillas", OPE, json={"codigo_rfid": "A1:B2:C3:D4"})
_rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0500'").fetchone()[0]
call("POST", f"/manillas/{_b['id']}/asignar", OPE, json={"recluso_id": _rid})

@tc("TC-026")
def _(p):
    k = api_key("Lector pabellón A")
    c, b = call("POST", "/dispositivos/lectura-rfid", key=k, json={"codigo_rfid": "A1B2C3D4"})
    p("Lector pabellón A lee la manilla A1:B2:C3:D4", f"HTTP {c}; reconocido={b.get('reconocido')}; recluso={b.get('recluso',{}).get('nombres')}; zona={b.get('zona')}", c == 200 and b.get("reconocido"))
    c, b = call("GET", "/ubicaciones", OPE)
    u = [x for x in b if x["codigo_interno"] == "SP-0500"]
    p("Consultar la ubicación de Ramiro Huanca", f"zona={u[0]['zona'] if u else None}", u and u[0]["zona"] == "Pabellón A")
    c, b = call("POST", "/dispositivos/lectura-rfid", key=k, json={"codigo_rfid": "DE:AD:BE:EF"})
    p("Lector lee una manilla desconocida DE:AD:BE:EF", f"HTTP {c}; {b}", c == 404)
    a = db().execute("SELECT tipo, severidad, descripcion FROM alertas ORDER BY id DESC LIMIT 1").fetchone()
    p("Revisar última alerta", f"{a}", a[0] == "suplantacion" and a[1] == "alta")
    c, b = call("POST", "/dispositivos/lectura-rfid", key="clave-falsa", json={"codigo_rfid": "A1B2C3D4"})
    p("Lectura enviada con API key inválida", f"HTTP {c}; {b.get('error')}", c == 401)

@tc("TC-027")
def _(p):
    k = api_key("Lector muro norte")
    c, b = call("POST", "/dispositivos/lectura-rfid", key=k, json={"codigo_rfid": "A1:B2:C3:D4"})
    p("Lector del muro perimetral norte lee la manilla de Ramiro Huanca", f"HTTP {c}; zona={b.get('zona')}", c == 200)
    a = db().execute("SELECT tipo, severidad, descripcion FROM alertas ORDER BY id DESC LIMIT 1").fetchone()
    p("Revisar alerta", f"{a}", a[0] == "zona_restringida" and a[1] == "critica")
    c, b = call("POST", "/recuento", OPE)
    pend = [x for x in b.get("pendientes", []) if "Ramiro" in x["nombre"]]
    p("Pasar lista (recuento)", f"HTTP {c}; esperados={b.get('esperados')}, ubicados={b.get('ubicados')}, por verificar={b.get('por_verificar')}; Ramiro: {pend[0]['motivo'] if pend else 'no figura'}", c == 201 and pend)

# ---------------- Telemetría ----------------
@tc("TC-028")
def _(p):
    k = api_key("Lector patio")
    c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "A1:B2:C3:D4", "bpm": 0, "contacto": False, "bateria": 80})
    p("Manilla reporta contacto=false (retirada)", f"HTTP {c}; alertas creadas={b.get('alertas')}", c == 200 and len(b.get("alertas", [])) == 1)
    a = db().execute("SELECT tipo, severidad FROM alertas WHERE id=?", (b["alertas"][0],)).fetchone()
    p("Revisar alerta", f"{a}", a == ("retiro_manilla", "critica"))
    c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "A1:B2:C3:D4", "contacto": False, "bateria": 80})
    p("Segunda lectura sin contacto (alerta aún pendiente)", f"HTTP {c}; alertas creadas={b.get('alertas')}", c == 200 and b.get("alertas") == [])
    c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "A1:B2:C3:D4", "bpm": 75, "contacto": True, "bateria": 10})
    p("Lectura con batería 10 % (< 15 %)", f"HTTP {c}; alertas={b.get('alertas')}", c == 200 and len(b.get("alertas", [])) == 1)

@tc("TC-029")
def _(p):
    k = api_key("Lector patio")
    rid = db().execute("SELECT id FROM reclusos WHERE codigo_interno='SP-0500'").fetchone()[0]
    def tel(bpm):
        return call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "A1:B2:C3:D4", "bpm": bpm, "contacto": True, "bateria": 90})
    for v in (140, 140, 140):
        c, b = tel(v)
    p("3 lecturas de 140 lpm (límite superior del rango 40-140)", f"HTTP {c}; alertas={b.get('alertas')}", c == 200 and b.get("alertas") == [])
    tel(141); c, b = tel(141)
    p("2 lecturas de 141 lpm (fuera de rango, no sostenido)", f"HTTP {c}; alertas={b.get('alertas')}", c == 200 and b.get("alertas") == [])
    c, b = tel(141)
    p("3ra lectura consecutiva de 141 lpm", f"HTTP {c}; alertas={b.get('alertas')}", c == 200 and len(b.get("alertas", [])) == 1)
    a = db().execute("SELECT tipo, severidad FROM alertas WHERE id=?", (b["alertas"][0],)).fetchone() if b.get("alertas") else None
    p("Revisar alerta", f"{a}", a == ("pulso_anormal", "media"))
    c, b = call("GET", "/manillas/monitoreo", OPE)
    m = [x for x in b if x["codigo_rfid"] == "A1:B2:C3:D4"]
    p("Ver monitoreo de la manilla", f"bpm actual={m[0]['bpm'] if m else None}; últimas lecturas={m[0]['lecturas'] if m else None}", m and m[0]["bpm"] == 141)

@tc("TC-030")
def _(p):
    k = api_key("Lector patio")
    c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "5C:88:0F:71", "bpm": "abc", "contacto": True, "bateria": 90})
    p("Telemetría de la manilla 5C:88:0F:71 (Marco Ticona) con bpm = 'abc'", f"HTTP {c}; respuesta: {str(b)[:60]}", c == 400)
    for _i in range(3):
        c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "5C:88:0F:71", "bpm": 150, "contacto": True, "bateria": 90})
        p(f"Lectura válida N° {_i+1} de 150 lpm (fuera de rango) de la misma manilla", f"HTTP {c}; respuesta: {str(b)[:60]}", c == 200)
    p("Resultado tras la 3ra lectura fuera de rango", f"alertas creadas = {b.get('alertas') if isinstance(b, dict) else 'ninguna'}", isinstance(b, dict) and len(b.get("alertas", [])) == 1)
    tipo = db().execute("SELECT typeof(bpm), bpm FROM lecturas_pulso l JOIN manillas m ON m.id=l.manilla_id WHERE m.codigo_rfid='5C:88:0F:71' AND typeof(bpm)='text'").fetchall()
    p("Buscar lecturas de pulso no numéricas guardadas en la base", f"{tipo}", not tipo)
    c, b = call("POST", "/dispositivos/telemetria", key=k, json={"codigo_rfid": "2D:4A:9E:06", "bpm": 72, "contacto": True, "bateria": 250})
    p("Telemetría de 2D:4A:9E:06 (René Choque) con batería = 250 %", f"HTTP {c}; {str(b)[:80]}", c == 400)
    row = db().execute("SELECT nivel_bateria FROM manillas WHERE codigo_rfid='2D:4A:9E:06'").fetchone()
    p("Revisar la batería guardada en la manilla", f"nivel_bateria = {row[0]} %", row[0] is not None and row[0] <= 100)

# ---------------- Eventos, alertas, reportes, auditoría ----------------
@tc("TC-031")
def _(p):
    c, b = call("GET", "/eventos?recluso_id=2", ADM)
    p("Filtrar eventos por recluso (Luis Condori, id 2)", f"HTTP {c}; {len(b)} eventos; todos del recluso 2: {all(e['recluso_id']==2 for e in b)}", c == 200 and b and all(e["recluso_id"] == 2 for e in b))
    c, b = call("GET", "/eventos?tipo=visita&resultado=fallo", ADM)
    p("Filtrar por tipo 'visita' y resultado 'fallo'", f"HTTP {c}; {len(b)} eventos", c == 200 and b and all(e["tipo"] == "visita" and e["resultado"] == "fallo" for e in b))
    hoy = dt.date.today().isoformat()
    c, b = call("GET", f"/eventos?desde={hoy}&hasta={hoy}", ADM)
    p(f"Filtrar por fecha de hoy ({hoy})", f"HTTP {c}; {len(b)} eventos", c == 200 and len(b) > 0)
    c, b = call("GET", "/eventos?desde=2000-01-01&hasta=2000-01-02", ADM)
    p("Filtrar por un rango sin eventos (año 2000)", f"HTTP {c}; {len(b)} eventos", c == 200 and len(b) == 0)

@tc("TC-032")
def _(p):
    c, b = call("GET", "/eventos?recluso_id=abc", ADM)
    p("Filtrar eventos con recluso_id = 'abc'", f"HTTP {c}; {str(b)[:120]}", c == 400)
    c, b = call("GET", "/eventos?limite=diez", ADM)
    p("Filtrar eventos con limite = 'diez'", f"HTTP {c}; {str(b)[:120]}", c == 400)

@tc("TC-033")
def _(p):
    aid = db().execute("SELECT id FROM alertas WHERE estado='pendiente' AND tipo='retiro_manilla' ORDER BY id DESC LIMIT 1").fetchone()[0]
    c, b = call("PATCH", f"/alertas/{aid}/atender", SUP, json={"nota": "Se verificó en el patio: manilla recolocada"})
    p("Supervisor atiende la alerta de retiro de manilla", f"HTTP {c}; {b.get('mensaje')}", c == 200)
    r = db().execute("SELECT estado, atendida_por, nota_atencion FROM alertas WHERE id=?", (aid,)).fetchone()
    p("Verificar la alerta en la base", f"{r}", r[0] == "atendida" and r[1] is not None)
    c, b = call("PATCH", f"/alertas/{aid}/atender", SUP, json={"nota": "otra vez"})
    p("Atender nuevamente la misma alerta", f"HTTP {c}; {b.get('error')}", c == 409)
    c, b = call("GET", "/alertas?estado=pendiente", OPE)
    p("Listar alertas pendientes", f"HTTP {c}; {len(b)} pendientes; la atendida no aparece: {all(x['id'] != aid for x in b)}", c == 200 and all(x["id"] != aid for x in b))

@tc("TC-034")
def _(p):
    c, b = call("GET", "/auditoria?limite=500", ADM)
    acciones = {x["accion"] for x in b}
    req = {"login", "login_fallido", "crear_usuario", "desactivar_usuario", "crear_recluso", "registrar_rostro", "asignar_manilla", "verificacion", "atender_alerta"}
    p("Consultar la auditoría como administrador", f"HTTP {c}; {len(b)} registros", c == 200)
    p("Comprobar acciones críticas registradas", f"faltan: {sorted(req - acciones) or 'ninguna'}", req <= acciones)
    p("Comprobar que la contraseña temporal no se guarda en la auditoría", f"'Inicial2026' en auditoría: {'Inicial2026' in json.dumps(b)}", "Inicial2026" not in json.dumps(b))

@tc("TC-035")
def _(p):
    c, b = call("POST", "/zonas", ADM, json={"nombre": "Taller de carpintería", "tipo": "comun", "orden": 10})
    p("Crear zona 'Taller de carpintería'", f"HTTP {c}; id={b.get('id')}", c == 201)
    c, b = call("POST", "/zonas", ADM, json={"nombre": "Taller de carpintería", "tipo": "comun"})
    p("Crear otra zona con el mismo nombre", f"HTTP {c}; {str(b)[:150]}", c == 409)
    c, b = call("POST", "/zonas", ADM, json={"nombre": "Zona X", "tipo": "otro"})
    p("Crear zona con tipo inválido", f"HTTP {c}; {b.get('error')}", c == 400)

json.dump(R, open(f"{OUT}/resultados.json", "w"), ensure_ascii=False, indent=1)
