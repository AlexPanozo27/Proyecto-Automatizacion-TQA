"""Pruebas no funcionales: rendimiento, estrés y resistencia (soak) sobre la API de SIBIO-RFID.
Los umbrales y tamaños se ajustan con variables de entorno (ver config/config.example.env)."""
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from soporte import FalloInfraestructura, caso

N = lambda k, d: int(os.environ.get(k, d))  # noqa: E731


def _rafaga(api, token, total, hilos, ruta="/api/dashboard"):
    def una(_):
        try:
            r = api.llamar("GET", ruta, token)
            return r.ms, r.status_code
        except FalloInfraestructura:
            return None, 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        res = list(ex.map(una, range(total)))
    dur = time.time() - t0
    tiempos = sorted(ms for ms, c in res if ms is not None and c == 200)
    errores = sum(1 for ms, c in res if c != 200)
    p95 = tiempos[int(len(tiempos) * 0.95) - 1] if tiempos else None
    med = round(statistics.median(tiempos)) if tiempos else None
    crudos = [ms for ms, c in res if ms is not None and c == 200]
    salto = max(1, len(crudos) // 150)
    return {"total": total, "ok": len(tiempos), "errores": errores, "p50": med, "p95": p95,
            "rps": round(total / dur, 1), "dur": round(dur, 1), "serie": crudos[::salto]}


def _grafica(titulo, serie, umbral=None, eje="petición", serie2=None, nombres=None):
    """Datos de una gráfica de líneas; la web y el PDF la dibujan."""
    return {"titulo": titulo, "valores": serie, "valores2": serie2, "umbral": umbral, "eje": eje,
            "nombres": nombres or ["Tiempo de respuesta (ms)"]}


def _txt(m):
    return (f"{m['ok']}/{m['total']} OK, {m['errores']} errores · mediana {m['p50']} ms · p95 {m['p95']} ms · "
            f"{m['rps']} pet/s en {m['dur']} s")


@caso("TC-NF-01", "Rendimiento: el tablero responde rápido con 10 usuarios", suites=["performance"],
      tipo="no_funcional", modulo="API · Centro de monitoreo",
      objetivo="Medir el tiempo de respuesta de GET /api/dashboard con carga normal.",
      precondiciones="SIBIO-RFID encendido; sesión de administrador.",
      datos="10 usuarios simultáneos × 10 peticiones (QA_PERF_USUARIOS, QA_PERF_PETICIONES); umbral p95 ≤ QA_PERF_P95_MS (800 ms)",
      resultado_esperado="0 errores y percentil 95 menor o igual al umbral.")
def test_rendimiento(sibio, token_admin, registro):
    u, n, umbral = N("QA_PERF_USUARIOS", 10), N("QA_PERF_PETICIONES", 10), N("QA_PERF_P95_MS", 800)
    with registro.paso(f"Enviar {u * n} peticiones con {u} usuarios simultáneos") as p:
        m = _rafaga(sibio, token_admin, u * n, u)
        p["observado"] = _txt(m)
        p["grafica"] = _grafica(f"Tiempo de respuesta de {u * n} peticiones con {u} usuarios", m["serie"], umbral)
    with registro.paso(f"Comprobar 0 errores y p95 ≤ {umbral} ms") as p:
        p["observado"] = f"p95 = {m['p95']} ms; errores = {m['errores']}"
        assert m["errores"] == 0, f"{m['errores']} peticiones fallaron"
        assert m["p95"] is not None and m["p95"] <= umbral, f"p95 de {m['p95']} ms supera el umbral de {umbral} ms"


@caso("TC-NF-02", "Estrés: 50 usuarios simultáneos sin errores del servidor", suites=["estres"],
      tipo="no_funcional", modulo="API",
      objetivo="Comprobar que el servidor aguanta una ráfaga alta de peticiones sin caerse.",
      precondiciones="SIBIO-RFID encendido (Waitress).",
      datos="50 usuarios × 10 peticiones (QA_ESTRES_USUARIOS, QA_ESTRES_PETICIONES)",
      resultado_esperado="Tasa de error ≤ 1 % y el servidor sigue respondiendo después de la ráfaga.")
def test_estres(sibio, token_admin, registro):
    u, n = N("QA_ESTRES_USUARIOS", 50), N("QA_ESTRES_PETICIONES", 10)
    with registro.paso(f"Lanzar una ráfaga de {u * n} peticiones con {u} hilos") as p:
        m = _rafaga(sibio, token_admin, u * n, u)
        p["observado"] = _txt(m)
        p["grafica"] = _grafica(f"Estrés: {u * n} peticiones con {u} usuarios simultáneos", m["serie"])
    with registro.paso("Comprobar tasa de error ≤ 1 %") as p:
        tasa = m["errores"] / m["total"] * 100
        p["observado"] = f"tasa de error {tasa:.2f} %"
        assert tasa <= 1, f"tasa de error {tasa:.1f} %"
    with registro.paso("Comprobar que el servidor sigue vivo tras la ráfaga") as p:
        r = sibio.llamar("GET", "/api/auth/yo", token_admin)
        p["observado"] = f"HTTP {r.status_code} en {r.ms} ms"
        assert r.status_code == 200


@caso("TC-NF-03", "Resistencia (soak): carga sostenida sin degradarse", suites=["soak"],
      tipo="no_funcional", modulo="API",
      objetivo="Mantener carga constante y comparar el tiempo de respuesta al inicio y al final.",
      precondiciones="SIBIO-RFID encendido.",
      datos="5 usuarios durante 30 s (QA_SOAK_SEGUNDOS, QA_SOAK_USUARIOS); degradación máxima 2×",
      resultado_esperado="0 errores y la mediana final no supera el doble de la inicial.")
def test_soak(sibio, token_admin, registro):
    seg, u = N("QA_SOAK_SEGUNDOS", 30), N("QA_SOAK_USUARIOS", 5)
    tramos = []
    with registro.paso(f"Mantener {u} usuarios durante {seg} s, midiendo cada tramo") as p:
        fin = time.time() + seg
        while time.time() < fin:
            tramos.append(_rafaga(sibio, token_admin, u * 4, u))
        p["observado"] = f"{len(tramos)} tramos; primero: {_txt(tramos[0])}; último: {_txt(tramos[-1])}"
        salto = max(1, len(tramos) // 150)
        p["grafica"] = _grafica(f"Resistencia: {u} usuarios durante {seg} s", [t["p50"] or 0 for t in tramos][::salto],
                                eje="tramo", serie2=[t["p95"] or 0 for t in tramos][::salto], nombres=["Mediana (ms)", "p95 (ms)"])
    with registro.paso("Comparar inicio contra final y contar errores") as p:
        errores = sum(t["errores"] for t in tramos)
        ini, fin_ = tramos[0]["p50"] or 1, tramos[-1]["p50"] or 1
        p["observado"] = f"mediana inicial {ini} ms → final {fin_} ms; errores totales {errores}"
        assert errores == 0, f"{errores} errores durante la carga sostenida"
        assert fin_ <= max(ini * 2, ini + 50), "el tiempo de respuesta se degradó más del doble"
