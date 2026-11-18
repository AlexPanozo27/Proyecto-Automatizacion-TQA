# Evidencias reales de ejecución (laptop)

Ejecutadas el 17/11/2026 (hora local Bolivia) en la laptop de desarrollo, contra SIBIO-RFID local (PostgreSQL, modo biometría simulado).

**Ambiente:** Windows 11 Home 10.0.26300 · Intel Core i5-13420H (8 núcleos / 12 hilos) · 15,7 GB RAM · Python 3.13.0 · pytest 9.2.0 · Playwright 1.65.2 con Microsoft Edge 157.0.4341.60 (ventana visible, 250 ms por acción) · Selenium 4.52.0 · Locust 2.47.0 · SIBIO-RFID commit af33629 (+ cambios locales) · QA Lab rama `claude/project-thread-lwki7s` @ a4972ca.

| Código | Suite | Ejecución | Inicio – fin | Duración | PASS | FAIL | ERROR | SKIPPED | NOT RUN | Correo |
|---|---|---|---|---|---|---|---|---|---|---|
| EV-01 | Smoke | EJ-20261117-024200-OR | 02:42:00 – 02:42:36 | 35,6 s | 5 | 0 | 0 | 0 | 0 | enviado |
| EV-02 | Regresión | EJ-20261117-024248-DW | 02:42:48 – 02:44:09 | 80,6 s | 12 | 1 | 0 | 1 | 0 | enviado |
| EV-03 | Rendimiento | EJ-20261117-024436-LB | 02:44:36 – 02:44:41 | 4,6 s | 1 | 0 | 0 | 0 | 0 | enviado |
| EV-04 | Estrés | EJ-20261117-024453-SK | 02:44:53 – 02:45:08 | 15,8 s | 1 | 0 | 0 | 0 | 0 | enviado |
| EV-05 | Soak | EJ-20261117-024521-MR | 02:45:21 – 02:46:01 | 40,3 s | 1 | 0 | 0 | 0 | 0 | enviado |
| EV-06 | Selenium WebDriver (complemento) | pytest complementos/selenium | — | 20,0 s | 2 | 0 | 0 | 0 | 0 | — |
| EV-07 | Locust (complemento, 30 usuarios, 2 min) | locust headless | — | 2 min | PASS | | | | | — |
| EV-08 | Retesting BUG-001..005 | EJ-20261117-024954-ZJ | 02:49:54 – 02:49:58 | 4,7 s | 0 | 5 | 0 | 0 | 0 | enviado |
| EV-09 | Seguridad | EJ-20261117-143614-EC | 14:36:14 – 14:36:23 | 8,6 s | 8 | 0 | 0 | 0 | 0 | enviado |
| EV-10 | Capacidad por escalones (Locust, 18/11) | locust headless × 4 | — | 4 × 50 s | — | 4 logins (300 u) | | | | — |

- EV-02: TC-E2E-04 FAIL controlado ("se esperaban 0 alertas pendientes y el panel muestra 32"); TC-API-10 SKIPPED (sensor de huella fuera de alcance, modo simulado).
- EV-03 (TC-NF-01): 100/100 OK, 0 errores · mediana 160 ms · p95 220 ms · 57,3 pet/s (umbral p95 ≤ 800 ms).
- EV-04 (TC-NF-02): 500/500 OK con 50 hilos, 0 errores · mediana 604 ms · p95 976 ms · 69,0 pet/s; servidor vivo después (HTTP 200 en 102 ms).
- EV-05 (TC-NF-03): 5 usuarios × 30 s, 42 tramos, 0 errores · mediana inicial 128 ms → final 172 ms.
- EV-07: 1641 peticiones, 0 errores, p50 150 ms, p95 260 ms, 14,0 pet/s (ver carga_stats.csv y carga.html).
- EV-08: ninguno de los defectos del Entregable 1 está cerrado: BUG-001, 003, 004 y 005 siguen abiertos y BUG-002 está corregido en parte (ver resultados.jsonl, observación de cada paso). BUG-006 (Reportes) se verificó a mano: PDF sí, Excel no.
- EV-09 (TC-SEG-01..08): 8/8 PASS; cadena de auditoría HMAC-SHA256 íntegra, bloqueo tras 5 intentos, 2FA, inyección SQL, cierre de sesión, sin datos sensibles ni trazas.
- EV-10: escalones de 60, 120, 200 y 300 usuarios (CSV, HTML, consola y gráficas por escalón). El login admite unas 2 sesiones por segundo: solo entraron 60, 96, 96 y 100 usuarios. Capacidad demostrada: unos 100 operadores activos, techo de unas 41 pet/s; con 300 usuarios, 4 logins fallidos.
- Los correos de destino se ocultaron en los JSON y en los PDF.
- manual/ (ejecución manual, 17/11/2026, ambiente local):
  | ID | Caso | Tester | Hora | Resultado esperado | Resultado obtenido | Estado | Evidencia |
  |---|---|---|---|---|---|---|---|
  | M-01 | Login correcto (qa_operador) | Alexander | 03:21 | Entra al panel con su rol y penal | Centro de monitoreo, "Bienvenido, QA Operador", rol Operador de control, penal San Pedro; sin menú de administración | PASS | M-01a, M-01b |
  | M-02 | Login con contraseña incorrecta | Claude (navegador integrado) | 02:51 | Mensaje genérico y aviso de bloqueo | "Usuario o contraseña incorrectos. Le quedan 4 intentos antes del bloqueo temporal." | PASS | M-02 |
  | M-03 | Buscar recluso "Quispe" (búsqueda global Ctrl+K) | Alexander | 03:22 | Aparece el recluso con su código SP-0412 | Búsqueda global: "Carlos Quispe Choque · SP-0412 · Pabellón A · Centro Penitenciario San Pedro". Módulo Reclusos (03:23): 1 resultado, tarjeta SP-0412 Carlos Quispe Choque, Pabellón A | PASS | M-03, M-03b |
  | M-04 | Login con contraseña vacía | Alexander | 03:20 aprox. | No deja entrar y pide los datos | "Escriba su usuario y su contraseña." | PASS | M-04 |

No se incluyen pytest.log, .env ni credenciales.
