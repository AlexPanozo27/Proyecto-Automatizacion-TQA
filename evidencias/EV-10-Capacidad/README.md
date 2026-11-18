# EV-10 · Capacidad por escalones con Locust

Ejecutado el 18/11/2026, entre las 15:59 y las 16:04 (hora de Bolivia), contra SIBIO-RFID en http://127.0.0.1:5000.

- Configuración: `locust -f complementos/locust/locustfile.py --headless -u N -r 10 -t 50s`, con 20 s de pausa entre escalones.
- Archivos: por cada escalón, reporte HTML (`uN.html`), CSV (`uN_stats.csv`, `uN_stats_history.csv`, `uN_failures.csv`), salida de consola (`uN_consola.txt`) y captura de las gráficas (`uN-graficas.png`).

## Resultados globales (fila Aggregated)

| Usuarios pedidos | Logins completados | Peticiones | Fallos | p50 (ms) | p95 (ms) | p99 (ms) | pet/s |
|---|---|---|---|---|---|---|---|
| 60  | 60  | 1297 | 0 | 160 | 1300 | 1700 | 26,9 |
| 120 | 96  | 1900 | 0 | 160 | 1800 | 2800 | 39,4 |
| 200 | 96  | 1977 | 0 | 160 | 830  | 2300 | 41,0 |
| 300 | 100 | 2002 | 4 | 150 | 860  | 2400 | 41,5 |

## p95 por endpoint (ms)

| Usuarios | /api/dashboard | /api/reclusos | /api/alertas | /api/auth/login |
|---|---|---|---|---|
| 60  | 400  | 300  | 940  | 1600 |
| 120 | 1400 | 1100 | 1300 | 4200 |
| 200 | 510  | 460  | 370  | 2600 |
| 300 | 450  | 390  | 430  | 2700 (4 rechazados) |

## Lectura correcta de estos resultados

- **El inicio de sesión es el cuello de botella.** Solo se completaron entre 96 y 100 inicios de sesión en cada escalón de 120, 200 y 300 usuarios. Por eso, en esos escalones nunca hubo más de unos 100 operadores con sesión activa. Los escalones de 200 y 300 **no** prueban 200 ni 300 usuarios activos.
- El throughput se estabiliza en unas **41 peticiones por segundo** a partir de 120 usuarios.
- El p95 alto de la fila Aggregated se debe a la subida inicial: ahí se acumulan logins, que son lentos porque verifican la contraseña con un hash costoso. En la parte estable (ver `u200-graficas.png`), el p95 de las consultas baja a unos 250–300 ms.
- Con 300 usuarios hubo 4 inicios de sesión rechazados por conexión (WinError 10061): el servidor dejó de aceptar conexiones nuevas por un momento.
- Justo al terminar, `/api/auth/opciones` no respondió en 10 s; un momento después respondió HTTP 200. El servidor se recuperó solo, sin reiniciarlo.
- El generador de carga y el servidor estaban en la misma laptop, así que los tiempos incluyen la competencia por CPU entre ambos.
