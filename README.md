# Proyecto-Automatizacion-TQA · QA Lab SIBIO-RFID

Plataforma web de **automatización de pruebas** de la materia **TQA-711 · Pruebas y Aseguramiento de la Calidad de Software** (UNIFRANZ, 02/2026). El sistema bajo prueba es **SIBIO-RFID** (biometría facial, huella y manilla RFID para recintos penitenciarios).

Desde la web se elige el **tipo de prueba** (funcional o no funcional), una **suite** o **casos sueltos** y un **correo**. Las pruebas se ejecutan de verdad contra SIBIO-RFID, la pantalla muestra el avance en vivo y al terminar llegan por correo **dos adjuntos**: un informe **PDF** detallado por caso y un informe **HTML** independiente con la tabla resumen.

## Qué cumple de la guía del docente

| Requisito | Cómo se cumple |
|---|---|
| Elegir tipo, suite o casos y correo validado | Web en `http://127.0.0.1:8080` (pasos 1, 2 y 3). El correo se valida en la página y en el servidor. |
| Ejecución real | `pytest` + `requests` contra la API REST, `Playwright` en el navegador contra el panel React, ráfagas concurrentes para carga. |
| Estados PASS / FAIL / SKIPPED / NOT RUN | Cada caso termina en uno de ellos; se muestran con **ícono y texto**, no solo color. |
| Fallo funcional vs. infraestructura | `FAIL` = una verificación no se cumplió. `ERROR` = SIBIO no responde, el navegador no abre o error del script. |
| Inicio, fin, duración y estado de la ejecución | Pendiente → En curso → Finalizada / Fallida / Cancelada, con ID único `EJ-AAAAMMDD-HHMMSS-XX`. |
| Informe PDF por caso | Objetivo, precondiciones, datos, resultado esperado, pasos con lo observado, **captura por paso** (E2E), error y **paso fallido**. |
| Informe HTML independiente | Tabla ID / nombre / tipo-suite / estado / observación, más los pasos de cada caso. |
| Correo | Asunto `Reporte de automatización – <Suite> – <fecha>`, SMTP en variables de entorno (`.env`). |
| Al menos un FAIL controlado | `TC-E2E-04` falla **a propósito** (espera 0 alertas pendientes y los datos demo siempre tienen). |
| Hardware fuera de alcance | `TC-API-10` (sensor de huella R307) sale **SKIPPED** si el sensor no está conectado. |

## Centro de mando, métricas e informes

- **Ejecución en vivo:** línea de tiempo de los casos, cada paso aparece mientras ocurre y se ve la última captura del navegador (o la gráfica de tiempos en las pruebas de carga).
- **Métricas de calidad:** salud de la versión, tasa de éxito global, tendencia de las últimas ejecuciones y los casos que más fallan.
- **Informe PDF:** portada con gráfica de dona y veredicto, índice de casos con enlaces, página de conclusiones (calculadas con los datos y, si hay clave, análisis de fallos con IA) y el detalle de cada caso con capturas y gráficas.
- **Modo Presentación** (paso 4 de la web, "Velocidad del navegador"): el navegador va más lento, muestra abajo un rótulo con el caso y el paso que se ejecuta y resalta en naranja cada elemento antes de usarlo. El rótulo y el resaltado se quitan antes de cada captura, así la evidencia muestra solo el panel, y el rótulo se dibuja con CSS para que ningún locator lo confunda con el sistema. Solo se nota con `QA_VER_NAVEGADOR=1`.
- **Cuenta regresiva del 2FA:** SIBIO no acepta dos veces el mismo código del autenticador. Si el código de estos 30 segundos ya se usó, la prueba espera al siguiente y la web muestra "Esperando un código 2FA nuevo: N s".
- **Asistente de IA:** cada locator del código se marca como real (con la pantalla del panel donde existe y su miniatura), dato de prueba o inventado.

## Asistente de IA

En la sección **Asistente de IA** se escribe un caso en español y la plataforma sigue el flujo que pide la guía:

1. **Caso** escrito por el usuario.
2. **Ambigüedades**: la IA lista lo que no está claro y el supuesto que tomará.
3. **Gherkin** en español (Característica / Escenario / Dado / Cuando / Entonces).
4. **Locators reales**: `motor/explorador.py` recorre el panel de SIBIO con Playwright y guarda los botones, campos y títulos que existen (unos 200 en 12 pantallas). La IA solo puede usar esos.
5. **Código** Playwright generado con los pasos y la evidencia del proyecto (`registro.paso`).
6. **Revisión** automática antes de ejecutar: sintaxis, nada de imports ni instrucciones peligrosas, cada locator comparado con el mapa real (✔ existe / ✖ inventado). El usuario puede editar el código; si algo no pasa, no se deja ejecutar.
7. **Ejecución**: se guarda como `tests/generados/test_ia_NN.py` (caso `TC-IA-NN`, suite *Generadas por IA*) y corre como cualquier otro caso, con capturas e informe.

Al terminar cada ejecución con fallos, la IA escribe un **análisis de fallos** (causa probable, funcional o de infraestructura, qué revisar) que aparece en la web, en el PDF, en el HTML y en el correo.

**Bug report con IA:** en una ejecución terminada, cada caso en FAIL tiene el botón "Bug report con IA". La IA redacta el reporte de defecto (título, severidad y prioridad con su justificación, pasos para reproducir, resultado obtenido, causa probable como hipótesis y recomendación). El ambiente, el resultado esperado y la evidencia no los escribe la IA: salen de la ejecución real. El reporte se puede copiar o descargar en Markdown (`reportes/<ejecución>/defectos/`), y avisa cuando la IA cree que no es un defecto real (por ejemplo, el FAIL controlado). Para un ERROR no se ofrece, porque es un problema del entorno y no un defecto de SIBIO.

**Jarvis** (botón redondo abajo a la derecha): chat con IA que conoce el proyecto (`docs/conocimiento_jarvis.md` + este README), el catálogo de casos y el historial real de ejecuciones. Explica teoría QA con los casos del proyecto (qué es Smoke, Regresión, funcional/no funcional…), cómo funciona el sistema (correo SMTP, infraestructura, autocuración), qué pasó en una ejecución y da sugerencias. Se le puede hablar con el micrófono (reconocimiento de voz del navegador, Edge/Chrome) y responder en voz alta (🔊). En cada ejecución terminada, el botón **"🤖 Explícamelo"** le pide que la explique en palabras simples. Solo responde con datos del proyecto y nunca muestra claves. En el Asistente IA, **"🎙 Dictar caso"** permite dictar el caso de prueba. **Jarvis ejecuta por orden:** "corre el Smoke" (o cualquier suite) → Jarvis pide confirmación → lanza la ejecución en vivo y al terminar cuenta el resultado; la orden se reconoce sin IA (instantánea, sin tokens). Arriba del chat, un selector elige el modelo: ⚡ Rápido (`gemini-flash-lite-latest`), 🧠 Potente (`gemini-3-flash-preview`) o 🔄 Auto (los del `.env`); bajo cada respuesta se muestra el modelo y los segundos. Jarvis saluda con voz (dile «llámame <nombre>»), narra la ejecución, al final explica los fallos y ofrece «Hazlo tú» (bug report, reparar, reintentar) o «Explícame cómo hacerlo yo»; 🔇 o «silencio» lo callan.

**Suite de Seguridad** (no funcional, 8 casos TC-SEG-01 a 08): cadena de auditoría HMAC-SHA256 íntegra y bien enlazada, bitácora que no se puede borrar por la API, bloqueo por fuerza bruta (con un usuario inventado), 2FA obligatoria para el administrador, inyección SQL sin efecto, token inválido tras cerrar sesión, sin contraseñas/secretos/plantillas biométricas en las respuestas y errores sin detalles internos. No modifica SIBIO: solo lee o usa cuentas inventadas. Nota: TC-SEG-04 envía un código 2FA falso; SIBIO bloquea el 2FA tras 5 fallos, así que no conviene correr esta suite más de 4 veces seguidas en 5 minutos.

**Autocuración con IA:** cuando una prueba falla porque un elemento del panel ya no existe (por ejemplo, un campo cambió de nombre), el caso muestra "Error del script: el elemento … no apareció" y el botón **"Reparar con IA"**. La plataforma toma el locator roto, busca en el mapa del panel real los elementos más parecidos y la IA elige el equivalente, siempre uno que existe (si propone algo fuera del mapa, se descarta). Se muestra el antes y el después; al aprobar, se corrige el archivo de la prueba (queda copia en `reportes/autocuracion/`) y el caso se vuelve a ejecutar. Para mostrarlo sin tocar SIBIO existe la suite **"Autocuración (demo IA)"** con TC-AC-01, un caso escrito para una versión anterior del panel ("Buscar internos"); no forma parte de Smoke, Regresión ni E2E. El botón "Restaurar demo" lo deja como al principio.

**Modelo de respaldo:** si Gemini no responde en `IA_ESPERA_S` segundos (40 por defecto) o está saturado (HTTP 429/5xx), la plataforma reintenta con `GEMINI_MODELO_RESPALDO` (por defecto `gemini-flash-lite-latest`) y lo avisa en pantalla. Un error de clave no se reintenta. Jarvis usa un modo rápido: Gemini 3 piensa en nivel `low` y pasa al respaldo a los `JARVIS_ESPERA_S` segundos (15 por defecto).

Proveedor: **Gemini** (clave gratuita en aistudio.google.com) o Claude, configurado en `.env`. Sin clave existe el modo `simulado`, con respuestas fijas, solo para probar la pantalla.

## Casos de prueba (22)

| Suite | Casos |
|---|---|
| Smoke | TC-API-01, 03, 07, 09 · TC-E2E-01 |
| Sanity | TC-API-01, 02, 04, 09 · TC-E2E-02 |
| Regresión | todos los funcionales (14) |
| Integración | TC-API-05, 07, 08, 10 |
| E2E (Playwright) | TC-E2E-01 a 04 |
| Rendimiento | TC-NF-01 (10 usuarios, p95 ≤ 800 ms) |
| Estrés | TC-NF-02 (50 usuarios simultáneos, error ≤ 1 %) |
| Soak | TC-NF-03 (carga sostenida, sin degradarse) |
| Retesting | TC-RT-01 a 05: vuelven a probar BUG-001 a BUG-005 del Entregable 1. Dan FAIL mientras el defecto siga abierto en SIBIO y PASS cuando se corrija |

Los casos viven en `tests/`. Cada uno tiene su ficha con `@caso(...)` (ID, suites, objetivo, precondiciones, datos, resultado esperado); la web lee el catálogo directamente de las pruebas, así que agregar un caso nuevo no requiere tocar la web.

## Cómo ejecutar (Windows)

1. Encender SIBIO-RFID con datos de demostración (`iniciar.bat` en `sistema-biometrico\backend`).
2. En esta carpeta: doble clic en **`instalar.bat`** (solo la primera vez).
3. Abrir `.env` y poner el correo SMTP (puede ser el mismo Gmail y contraseña de aplicación de SIBIO).
4. Doble clic en **`iniciar.bat`**: se abre `http://127.0.0.1:8080`.

Sin interfaz (por consola):

```
python -m pytest tests --suite smoke --salida reportes/consola
python -m pytest tests --casos TC-API-01,TC-E2E-04 --salida reportes/consola
```

### Complementos con herramientas del curso

La herramienta principal es **Playwright** (espera sola a los elementos, saca una captura por paso y se integra con pytest y la web). Como complemento:

- **Selenium WebDriver** (`complementos/selenium/test_login_selenium.py`): TC-E2E-01 y TC-E2E-02 con `By.ID`, `By.CSS_SELECTOR`, `By.XPATH` y esperas explícitas. En Windows usa Microsoft Edge; Selenium Manager descarga el driver solo.

```
python -m pytest complementos/selenium -v
```

- **Locust** (`complementos/locust/locustfile.py`): carga sobre la API con usuarios virtuales "operador de turno" (login, Centro de monitoreo, búsqueda de reclusos, alertas). Termina con PASS si p95 ≤ 800 ms y 0 errores.

```
locust -f complementos/locust/locustfile.py --host http://127.0.0.1:5000 --headless -u 30 -r 5 -t 2m --html reportes/locust/carga.html
```

Sin `--headless` se abre la interfaz de Locust en `http://localhost:8089` con gráficas en vivo.

## Estructura

```
app.py                  Web Flask (API de ejecuciones + página)
web/index.html          Interfaz (configurar, ver en vivo, historial)
motor/ejecutor.py       Lanza pytest en segundo plano y sigue el avance
motor/informes.py       Genera el HTML y el PDF (HTML → PDF con Chromium)
motor/correo.py         Valida el correo y envía los adjuntos por SMTP
plantillas/             Plantillas de los informes
tests/conftest.py       Plugin: --suite, --casos, estados, clasificación FAIL/ERROR
tests/soporte.py        @caso, pasos con evidencia y cliente de la API
tests/api/              Pruebas funcionales de la API
tests/e2e/              Pruebas del panel con Playwright
tests/no_funcional/     Rendimiento, estrés y soak
reportes/               Una carpeta por ejecución (no se sube a GitHub)
legado/                 Script del Entregable 1 (versión anterior, solo referencia)
```

> Solo se usan datos y usuarios ficticios del modo demostración. No se versionan `.env`, contraseñas reales ni bases de datos.

## Autor

Marcos Alexander Panozo Patty · UNIFRANZ
