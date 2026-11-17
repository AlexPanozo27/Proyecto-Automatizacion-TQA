"""
Prueba de carga con Locust sobre la API de SIBIO-RFID (complemento de TC-NF-01..03).

Cada usuario virtual es un operador de turno: inicia sesión una vez y luego, con pausas de 1 a 3 s,
consulta el Centro de monitoreo (lo más frecuente), busca reclusos y revisa alertas.

Ejecutar (con SIBIO encendido), desde la carpeta del proyecto:
    locust -f complementos/locust/locustfile.py --host http://127.0.0.1:5000 ^
           --headless -u 30 -r 5 -t 2m --html reportes/locust/carga.html
Interfaz web de Locust (gráficas en vivo): quitar --headless y abrir http://localhost:8089

Usuario y contraseña salen de variables de entorno (.env), nunca del código.
Criterio propuesto para el proyecto: p95 <= QA_PERF_P95_MS (800 ms) y 0 % de errores.
"""
import os
import random

from locust import HttpUser, between, events, task

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

USUARIO = os.environ.get("SIBIO_OPERADOR", "jperez")
CLAVE = os.environ.get("SIBIO_OPERADOR_CLAVE", "")
P95_MAX = int(os.environ.get("QA_PERF_P95_MS", "800"))
BUSQUEDAS = ["Quispe", "Mamani", "Condori", "Flores", "SP-0", "zzz-sin-resultado"]


class OperadorDeTurno(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        r = self.client.post("/api/auth/login", json={"username": USUARIO, "password": CLAVE}, name="POST /api/auth/login")
        if r.status_code != 200 or "token" not in r.json():
            raise RuntimeError(f"El usuario de pruebas no pudo iniciar sesión (HTTP {r.status_code})")
        self.client.headers["Authorization"] = "Bearer " + r.json()["token"]

    @task(5)
    def centro_de_monitoreo(self):
        self.client.get("/api/dashboard", name="GET /api/dashboard")

    @task(3)
    def buscar_recluso(self):
        self.client.get("/api/reclusos", params={"q": random.choice(BUSQUEDAS)}, name="GET /api/reclusos?q=")

    @task(2)
    def revisar_alertas(self):
        self.client.get("/api/alertas", name="GET /api/alertas")


@events.quitting.add_listener
def veredicto(environment, **_kw):
    """Al terminar: falla (código de salida 1) si p95 supera el umbral o hubo errores."""
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95) or 0
    print(f"\n[QA] peticiones={total.num_requests} errores={total.num_failures} "
          f"p50={total.median_response_time} ms p95={p95} ms pet/s={total.total_rps:.1f} (umbral p95 {P95_MAX} ms)")
    if total.num_failures or p95 > P95_MAX:
        environment.process_exit_code = 1
        print("[QA] Resultado: FAIL")
    else:
        print("[QA] Resultado: PASS")
