# Proyecto-Automatizacion-TQA · QA Lab SIBIO-RFID

Plataforma web de **automatización de pruebas** del Proyecto Integrador de la materia **TQA-711 · Pruebas y Aseguramiento de la Calidad de Software** (UNIFRANZ, 02/2026). Autor: Marcos Alexander Panozo Patty. Docente: Ing. Reynel Sánchez Chuquimia.

## Objetivo

Seleccionar, ejecutar, documentar, reportar y comunicar pruebas de software desde una sola interfaz web. El sistema bajo prueba es **SIBIO-RFID** (control biométrico con rostro, huella y manilla RFID para recintos penitenciarios), cuyo código está en el repositorio [`AlexPanozo27/sibio-rfid`](https://github.com/AlexPanozo27/sibio-rfid) (privado; acceso por invitación).

Desde la web se elige el **tipo de prueba** (funcional o no funcional), una **suite** o **casos sueltos** y un **correo**. Las pruebas se ejecutan de verdad contra SIBIO-RFID, la pantalla muestra el avance en vivo y al terminar llegan por correo **dos adjuntos**: un informe **PDF** detallado por caso y un informe **HTML** independiente con la tabla resumen. Como plus, un **asistente de IA** convierte casos en lenguaje natural a Gherkin y a código, resume fallos, redacta bug reports y repara localizadores rotos.

## Contenido

1. [Cómo se cumple la guía del docente](#cómo-se-cumple-la-guía-del-docente)
2. [Tecnologías](#tecnologías)
3. [Requisitos](#requisitos)
4. [Instalación paso a paso (desde cero)](#instalación-paso-a-paso-desde-cero)
5. [Variables de entorno](#variables-de-entorno)
6. [Datos de prueba](#datos-de-prueba)
7. [Cómo ejecutar y guion de demostración](#cómo-ejecutar-y-guion-de-demostración)
8. [Funciones de la plataforma](#centro-de-mando-métricas-e-informes) · [Asistente de IA](#asistente-de-ia) · [Casos de prueba](#casos-de-prueba-30--demostraciones) · [Evidencias](#evidencias-y-documentación)
9. [Estructura del repositorio](#estructura-del-repositorio)
10. [Solución de problemas](#solución-de-problemas)

## Cómo se cumple la guía del docente

**Entregables (sección 6 de la guía):**

| Entregable que pide la guía | Dónde está en este repositorio |
|---|---|
| Frontend | `web/index.html` (página única: configurar, ver en vivo, historial, métricas, asistente de IA y Jarvis) |
| Backend / orquestador | `app.py` (API Flask de ejecuciones) y `motor/ejecutor.py` (lanza pytest en segundo plano y sigue el avance) |
| Pruebas | `tests/` (API, E2E, no funcionales, seguridad, retesting, demo de autocuración, generadas por IA) y `complementos/` (Selenium y Locust) |
| Generadores de reportes | `motor/informes.py` + `plantillas/` (PDF por caso y HTML independiente) y `motor/correo.py` (envío SMTP) |
| README (objetivo, tecnologías, requisitos, instalación, variables de entorno, ejecución) | Este archivo |
| Datos de prueba sin publicar secretos | [Datos de prueba](#datos-de-prueba); `config/config.example.env` no trae claves reales |
| Ejemplos de reportes con PASS y al menos un FAIL controlado | `ejemplos/` (Regresión con FAIL controlado) y `evidencias/` (EV-01 a EV-10) |
| Funcionalidad de IA | `motor/ia.py`, `motor/jarvis.py`, `motor/explorador.py` y `tests/generados/` |
| Documento de estrategia y ejecución | `docs/Capitulo6-Estrategia-y-Ejecucion-de-Pruebas-SIBIO-RFID.pdf` |

**Funcionalidades:**

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


## Tecnologías

| Capa | Herramienta | Para qué se usa |
|---|---|---|
| Lenguaje | Python 3.11+ | Toda la plataforma y las pruebas |
| Backend / orquestador | Flask 3 + Waitress | API de ejecuciones y servidor de la web (`app.py`) |
| Frontend | HTML + CSS + JavaScript (sin frameworks) | `web/index.html`: configurar, ver en vivo, historial, métricas, IA, Jarvis |
| Motor de pruebas | pytest 8+ (con un plugin propio en `tests/conftest.py`) | Suites, selección de casos, estados PASS/FAIL/ERROR/SKIPPED/NOT RUN |
| Pruebas de API | requests | Pruebas funcionales contra la API REST de SIBIO-RFID |
| Pruebas E2E | Playwright (Chromium) | Recorre el panel React de SIBIO con captura de pantalla por paso |
| Complemento E2E | Selenium WebDriver 4 (Edge/Chrome) | TC-E2E-01 y 02 con `By.ID`, `By.CSS_SELECTOR`, `By.XPATH` |
| No funcionales | Hilos concurrentes con requests · Locust | Rendimiento, estrés, soak y capacidad |
| Reportes | Jinja2 + Chromium (HTML → PDF) | Informe PDF por caso e informe HTML independiente |
| Correo | SMTP (Gmail con contraseña de aplicación) | Envío de los dos adjuntos |
| IA | Google Gemini (o Claude, o modo `simulado`) | Gherkin, ambigüedades, código, resumen de fallos, bug report, autocuración, Jarvis |
| Configuración | python-dotenv (`.env`) | Secretos y parámetros fuera del código |
| Sistema bajo prueba | SIBIO-RFID: Flask + PostgreSQL/SQLite + panel React (Vite) | Repositorio `sibio-rfid` |

## Requisitos

| Requisito | Versión | Para qué | Cómo comprobarlo |
|---|---|---|---|
| Windows | 10 u 11 | Los scripts `.bat` (en Linux/macOS se usan los mismos comandos de Python a mano) | — |
| Python | 3.11 o superior (probado con 3.13.0) | QA Lab y backend de SIBIO | `python --version` |
| Git | cualquiera reciente | Clonar los dos repositorios | `git --version` |
| Node.js | 18 o superior (probado con 24) | Compilar el panel React de SIBIO (una sola vez) | `node --version` |
| Navegador | Microsoft Edge o Google Chrome | Usar la web; Edge para el dictado por voz de Jarvis y para Selenium | — |
| PostgreSQL | 14+ (opcional) | Base de datos de SIBIO; sin él, SIBIO funciona con SQLite | — |
| Cuenta de Gmail | con verificación en 2 pasos | Crear una *contraseña de aplicación* para enviar los informes | — |
| Clave de Gemini | gratuita (opcional) | Funciones de IA; sin clave se usa el modo `simulado` | — |
| App autenticadora | Google/Microsoft Authenticator | SIBIO exige 2FA al administrador | — |
| Conexión a internet | — | Instalar librerías, descargar Chromium, enviar correo y usar la IA | — |

Espacio en disco: unos 1,5 GB (librerías de Python, Chromium de Playwright y `node_modules` del panel).

## Instalación paso a paso (desde cero)

Tiempo estimado: 30 a 40 minutos la primera vez. Todo se hace una sola vez; después solo se usan los `iniciar.bat`.

### Paso 0. Instalar los programas base

1. **Python**: descargar de <https://www.python.org/downloads/windows/> el *Windows installer (64-bit)*. En la primera pantalla marcar **☑ Add python.exe to PATH** y luego *Install Now*. Si al escribir `python` se abre la Microsoft Store, desactivar `python.exe` en *Configuración → Aplicaciones → Configuración avanzada → Alias de ejecución de aplicaciones*.
2. **Git**: <https://git-scm.com/download/win> (opciones por defecto).
3. **Node.js**: <https://nodejs.org> versión LTS (opciones por defecto).
4. Abrir una ventana nueva de *Símbolo del sistema* (`cmd`) y comprobar:
   ```
   python --version
   git --version
   node --version
   ```

### Paso 1. Clonar los dos repositorios

Usar una carpeta fuera de OneDrive, por ejemplo `C:\proyectos` (OneDrive bloquea o enlentece los miles de archivos que se generan):

```
mkdir C:\proyectos
cd C:\proyectos
git clone https://github.com/AlexPanozo27/sibio-rfid.git
git clone https://github.com/AlexPanozo27/Proyecto-Automatizacion-TQA.git
```

> `sibio-rfid` es privado: antes hay que aceptar la invitación de colaborador que llega por correo (o descargarlo como ZIP desde GitHub con la cuenta invitada). Si Git pide usuario y contraseña, iniciar sesión con la cuenta de GitHub invitada.

Quedan dos carpetas: `C:\proyectos\sibio-rfid` y `C:\proyectos\Proyecto-Automatizacion-TQA`.

### Paso 2. Instalar y encender SIBIO-RFID (sistema bajo prueba)

La guía detallada está en `sibio-rfid\GUIA_INSTALACION.md`. Resumen:

1. **Backend**: doble clic en `C:\proyectos\sibio-rfid\backend\instalar.bat`. Crea su entorno virtual, instala las librerías y pregunta:
   - Base de datos: `1` PostgreSQL (si está instalado) o `2` SQLite (más rápido para probar).
   - Contraseña del usuario `admin`: inventarla (mínimo 8 caracteres) y **anotarla**: se usa en el paso 3.
   - ¿Cargar datos de demostración?: Enter (**sí**; las pruebas necesitan esos datos).
2. **Panel web**: al terminar, el mismo `instalar.bat` compila el panel React (`npm install` + `npm run build`) si Node.js está instalado; el servidor de SIBIO lo sirve en el puerto 5000. Si no había Node.js o falló la compilación, hacerlo a mano una vez:
   ```
   cd C:\proyectos\sibio-rfid\frontend-v2
   npm install
   npm run build
   ```
   Debe aparecer la carpeta `frontend-v2\dist`. Sin ella, las pruebas E2E dan ERROR porque el panel no existe.
3. **Encender**: doble clic en `C:\proyectos\sibio-rfid\backend\iniciar.bat` y **dejar abierta** esa ventana. Si Windows pregunta por el Firewall, permitir en *Redes privadas*.
4. **Comprobar**: abrir <http://127.0.0.1:5000> y entrar con `jperez` (operador, ver [Datos de prueba](#datos-de-prueba)). Debe verse el Centro de monitoreo con datos.
5. **2FA del administrador**: SIBIO exige verificación en dos pasos al rol administrador. Entrar con `admin`, abrir **Mi cuenta** (el círculo con las iniciales, arriba a la derecha) → **Verificación en dos pasos**, escanear el QR con la app autenticadora y **copiar la "clave manual"** que se muestra (texto en base32). Esa clave va en `SIBIO_ADMIN_TOTP` del paso 3; con ella las pruebas generan solas el código de 6 dígitos.

### Paso 3. Instalar el QA Lab

1. Doble clic en `C:\proyectos\Proyecto-Automatizacion-TQA\instalar.bat`. El script:
   1. verifica que haya Python 3.11 o superior,
   2. crea el entorno virtual `.venv` (las librerías no se mezclan con las del sistema),
   3. instala `requirements.txt` (Flask, pytest, Playwright, Selenium, Locust, Jinja2…),
   4. descarga el navegador Chromium de Playwright (unos 150 MB),
   5. crea `.env` a partir de `config\config.example.env` (si ya existe, no lo toca).
2. Abrir `.env` con el Bloc de notas o VS Code y completar como mínimo:

   | Variable | Valor |
   |---|---|
   | `SIBIO_ADMIN_CLAVE` | la contraseña de `admin` creada en el paso 2.1 |
   | `SIBIO_OPERADOR_CLAVE` y `SIBIO_SUPERVISOR_CLAVE` | la clave de los usuarios de demostración (ver [Datos de prueba](#datos-de-prueba)) |
   | `SIBIO_ADMIN_TOTP` | la clave manual del 2FA del paso 2.5 |
   | `SMTP_USUARIO` y `SMTP_CLAVE` | el Gmail que envía y su *contraseña de aplicación* (<https://myaccount.google.com/apppasswords>; requiere la verificación en 2 pasos de Google activa) |
   | `GEMINI_API_KEY` | opcional: clave gratuita de <https://aistudio.google.com> → *Get API key*. Sin clave, poner `IA_PROVEEDOR=simulado` |
   | `SIBIO_DOCS_DIR` | opcional: `C:\proyectos\sibio-rfid`, para que Jarvis lea la documentación de SIBIO |

   El resto de variables ya trae valores que funcionan (ver [Variables de entorno](#variables-de-entorno)).

### Paso 4. Iniciar el QA Lab

1. Con SIBIO encendido (paso 2.3), doble clic en `iniciar.bat`.
2. Se abre la ventana del servidor y el navegador en <http://127.0.0.1:8080>. Dejar la ventana abierta mientras se usa.

### Paso 5. Verificar que la instalación quedó bien

Desde `C:\proyectos\Proyecto-Automatizacion-TQA` en `cmd`:

```
.venv\Scripts\activate
python -m pytest tests --collect-only -q
python -m pytest tests --suite smoke --salida reportes/consola
```

- El primer comando debe terminar en **`32 tests collected`** sin errores de importación (30 casos + TC-AC-01 + TC-IA-01).
- El segundo ejecuta el Smoke (5 casos, unos 40 s) y debe dar **5 PASS**. Los informes quedan en `reportes/consola/`.
- En la web, la cabecera debe decir **"SIBIO-RFID en línea · N ms"**; si dice "SIBIO-RFID no responde", SIBIO no está encendido o `SIBIO_URL` está mal.

## Variables de entorno

Se definen en `.env` (no se sube a GitHub; `.gitignore` lo excluye). La plantilla completa es `config/config.example.env`.

| Variable | Por defecto | Obligatoria | Descripción |
|---|---|---|---|
| `SIBIO_URL` | `http://127.0.0.1:5000` | sí | Dirección de SIBIO-RFID (API y panel) |
| `SIBIO_ADMIN` / `SIBIO_ADMIN_CLAVE` | `admin` / — | sí | Administrador de pruebas |
| `SIBIO_ADMIN_TOTP` | vacío | si el admin tiene 2FA | Clave manual (base32) del 2FA del administrador |
| `SIBIO_OPERADOR` / `SIBIO_OPERADOR_CLAVE` | `jperez` / — | sí | Usuario con rol operador |
| `SIBIO_SUPERVISOR` / `SIBIO_SUPERVISOR_CLAVE` | `agutierrez` / — | sí | Usuario con rol supervisor |
| `SIBIO_DOCS_DIR` | carpeta de arriba | no | Carpeta de `sibio-rfid`; Jarvis lee su README y su análisis por módulo |
| `SMTP_USUARIO` / `SMTP_CLAVE` | vacío | para enviar correo | Cuenta y contraseña de aplicación. Si faltan, el informe queda para descargar en la web |
| `SMTP_SERVIDOR` / `SMTP_PUERTO` | `smtp.gmail.com` / `587` | no | Servidor SMTP (STARTTLS) |
| `SMTP_NOMBRE` | `QA Lab SIBIO-RFID` | no | Nombre del remitente |
| `QA_PUERTO` / `QA_HOST` | `8080` / `127.0.0.1` | no | Dónde escucha la web del QA Lab |
| `QA_VER_NAVEGADOR` | `1` | no | `1` = se ve el navegador durante las E2E (demo); `0` = oculto y más rápido |
| `QA_LENTO_MS` / `QA_PRESENTACION_MS` | `250` / `450` | no | Pausa entre acciones con navegador visible / en modo Presentación |
| `CHROMIUM_PATH` | vacío | no | Usar un Edge/Chrome instalado en lugar del Chromium de Playwright |
| `SELENIUM_NAVEGADOR` / `SELENIUM_OCULTO` | `edge` / `0` | no | Navegador del complemento Selenium y si se muestra |
| `QA_PERF_USUARIOS` / `QA_PERF_PETICIONES` / `QA_PERF_P95_MS` | `10` / `10` / `800` | no | TC-NF-01 Rendimiento: usuarios, peticiones por usuario y umbral p95 |
| `QA_ESTRES_USUARIOS` / `QA_ESTRES_PETICIONES` | `50` / `10` | no | TC-NF-02 Estrés |
| `QA_SOAK_SEGUNDOS` / `QA_SOAK_USUARIOS` | `30` / `5` | no | TC-NF-03 Soak (carga sostenida) |
| `IA_PROVEEDOR` | `gemini` | no | `gemini`, `claude` o `simulado` (respuestas fijas, sin clave) |
| `GEMINI_API_KEY` | vacío | para la IA real | Clave de Google AI Studio |
| `GEMINI_MODELO` / `GEMINI_MODELO_RESPALDO` | `gemini-3-flash-preview` / `gemini-flash-lite-latest` | no | Modelo principal y de respaldo |
| `IA_ESPERA_S` / `JARVIS_ESPERA_S` | `40` / `15` | no | Segundos antes de pasar al modelo de respaldo |
| `ANTHROPIC_API_KEY` / `CLAUDE_MODELO` | vacío | si `IA_PROVEEDOR=claude` | Proveedor alternativo de IA |

## Datos de prueba

Solo se usan **usuarios y datos ficticios** del modo demostración de SIBIO-RFID (los carga `instalar.bat` de SIBIO al responder *sí* a "¿Cargar datos de demostración?"):

| Usuario | Rol | Lo usan | Clave |
|---|---|---|---|
| `admin` | Administrador (con 2FA obligatoria) | Pruebas que crean o consultan con permisos completos, seguridad, IA | La define quien instala SIBIO (paso 2.1) |
| `jperez` | Operador | Login, búsqueda de reclusos, E2E, Selenium, Locust | Clave de demostración de SIBIO: está en `sibio-rfid\GUIA_INSTALACION.md` (paso 5); no se publica aquí |
| `agutierrez` | Supervisor | Permisos por rol | La misma clave de demostración |

- Los datos demo incluyen reclusos, manillas RFID, zonas, alertas pendientes (el FAIL controlado TC-E2E-04 cuenta con ellas) y eventos.
- La suite de seguridad no modifica SIBIO: solo lee y usa un **usuario inventado** para probar el bloqueo por fuerza bruta.
- No se versionan `.env`, contraseñas reales, claves de API ni bases de datos. En `evidencias/` los correos de destino están ocultos.

## Cómo ejecutar y guion de demostración

Orden de encendido, cada vez que se use: **1)** `sibio-rfid\backend\iniciar.bat` → **2)** `Proyecto-Automatizacion-TQA\iniciar.bat` → navegador en <http://127.0.0.1:8080>.

### Desde la web (flujo de la demostración)

1. Comprobar en la cabecera: **"SIBIO-RFID en línea"**.
2. **1 · Tipo de prueba**: *Funcional* (o *No funcional* para rendimiento, estrés, soak y seguridad).
3. **2 · Qué ejecutar**: *Por suite* (por ejemplo **Regresión**, que incluye el FAIL controlado) o *Casos sueltos* (marcar los casos).
4. **3 · Correo para el informe**: escribir el correo destino; la página avisa si el formato no es válido (también se valida en el servidor).
5. **4 · Velocidad del navegador**: *Normal* o *Presentación* (más lento, con rótulo del paso y resaltado; útil frente al docente).
6. Clic en **Ejecutar pruebas**. El Centro de mando muestra el estado (Pendiente → En curso → Finalizada / Fallida), el ID `EJ-AAAAMMDD-HHMMSS-XX`, la línea de tiempo de casos y el navegador trabajando solo.
7. Al terminar: resumen con PASS / FAIL / ERROR / SKIPPED / NOT RUN, inicio, fin y duración, análisis de fallos con IA y botones **📄 Informe PDF** y **🌐 Informe HTML**.
8. Abrir el correo recibido: asunto `Reporte de automatización – Regresión – <fecha>` con los **dos adjuntos**.
9. Plus de IA: en el caso FAIL, **"Bug report con IA"**; en **Asistente de IA**, escribir un caso en español → ambigüedades → Gherkin → código con localizadores reales → ejecutar; suite **Autocuración (demo IA)** → **"Reparar con IA"**; **Jarvis** (botón redondo): "corre el Smoke".

### Por consola (sin interfaz)

Con el entorno virtual activo (`.venv\Scripts\activate`):

```
python -m pytest tests --suite smoke --salida reportes/consola
python -m pytest tests --suite regression --salida reportes/consola
python -m pytest tests --casos TC-API-01,TC-E2E-04 --salida reportes/consola
```

Los informes PDF y HTML de cada ejecución quedan en `reportes/<carpeta>/`.

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

## Casos de prueba (30 + demostraciones)

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
| Seguridad | TC-SEG-01 a 08: cadena de auditoría HMAC-SHA256, bitácora inalterable, bloqueo tras 5 intentos, 2FA, inyección SQL, cierre de sesión, datos sensibles y errores sin trazas. Ejecutar una vez seguida (TC-SEG-04 envía un código 2FA falso) |
| Autocuración (demo) | TC-AC-01: usa un localizador de una versión anterior del panel; la IA propone el nuevo, el tester aprueba y se vuelve a ejecutar. Botón "Restaurar demo" para dejarlo como estaba |
| Generadas por IA | TC-IA-NN: casos creados con el asistente (caso en español → Gherkin → código Playwright con localizadores reales), guardados en `tests/generados/` |

Los casos viven en `tests/`. Cada uno tiene su ficha con `@caso(...)` (ID, suites, objetivo, precondiciones, datos, resultado esperado); la web lee el catálogo directamente de las pruebas, así que agregar un caso nuevo no requiere tocar la web.

## Evidencias y documentación

- `evidencias/`: ejecuciones reales EV-01 a EV-10 (PDF por caso, HTML resumen, `ejecucion.json` y `resultados.jsonl` con cada paso), Selenium, Locust, capacidad por escalones y pruebas manuales. Ver `evidencias/README.md`.
- `docs/Capitulo6-Estrategia-y-Ejecucion-de-Pruebas-SIBIO-RFID.pdf`: el capítulo 6 (plan, automatización, no funcionales, ejecución, trazabilidad, resultados y anexos).
- `ejemplos/`: un informe PDF y HTML de muestra con el FAIL controlado.

Resumen (17-18/11/2026): Smoke 5/5 PASS · Regresión 12 PASS, 1 FAIL controlado, 1 SKIPPED · Seguridad 8/8 PASS · No funcionales 3/3 PASS · Retesting 5 FAIL (defectos aún abiertos en SIBIO) · Locust 30 usuarios: 0 errores, p95 260 ms · Capacidad: unos 100 operadores activos, techo de unas 41 pet/s (el login es el cuello de botella).

## Jarvis (asistente con voz)

Botón flotante en la web. Responde con datos reales del proyecto (catálogo, historial, documentación de la API de SIBIO), ejecuta suites por orden ("corre el Smoke", con confirmación), narra el avance con voz, explica cada fallo y ofrece "Hazlo tú" (bug report, reparar, reintentar) o "Explícame cómo". Dictado por voz: usar Microsoft Edge (Brave no trae reconocimiento de voz).

## Complementos con herramientas del curso

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


## Estructura del repositorio

```
Proyecto-Automatizacion-TQA/
├── app.py                  Backend/orquestador: web Flask (API de ejecuciones + página)
├── instalar.bat            Instalación: entorno .venv, librerías, Chromium y .env
├── iniciar.bat             Arranca la web en http://127.0.0.1:8080
├── requirements.txt        Librerías de Python
├── pytest.ini              Configuración de pytest
├── config/
│   └── config.example.env  Plantilla de variables de entorno (sin secretos)
├── web/
│   └── index.html          Frontend: configurar, ver en vivo, historial, métricas, IA, Jarvis
├── motor/
│   ├── ejecutor.py         Lanza pytest en segundo plano y sigue el avance
│   ├── informes.py         Genera el HTML y el PDF (HTML → PDF con Chromium)
│   ├── correo.py           Valida el correo y envía los adjuntos por SMTP
│   ├── ia.py               IA: Gherkin, código, resumen de fallos, bug report, autocuración
│   ├── jarvis.py           Asistente conversacional con voz
│   └── explorador.py       Mapa de localizadores reales del panel de SIBIO
├── plantillas/             Plantillas Jinja2 de los informes
├── tests/
│   ├── conftest.py         Plugin: --suite, --casos, estados, clasificación FAIL/ERROR
│   ├── soporte.py          @caso, pasos con evidencia, cliente de la API, 2FA
│   ├── ayudas_e2e.py       Ayudas comunes de Playwright
│   ├── api/                Pruebas funcionales de la API y retesting
│   ├── e2e/                Pruebas del panel con Playwright
│   ├── no_funcional/       Rendimiento, estrés y soak
│   ├── seguridad/          Pruebas de seguridad (TC-SEG)
│   ├── demo/               Demostración de autocuración (TC-AC-01)
│   └── generados/          Casos creados con el asistente de IA (TC-IA)
├── complementos/           Selenium WebDriver y Locust
├── docs/                   Capítulo 6 (PDF), API de SIBIO, conocimiento de Jarvis, mejoras propuestas
├── ejemplos/               Informe PDF y HTML de muestra con el FAIL controlado
├── evidencias/             Ejecuciones reales EV-01 a EV-10 y pruebas manuales
├── legado/                 Script del Entregable 1 (versión anterior, solo referencia)
└── reportes/               Se crea al ejecutar: una carpeta por ejecución (no se sube a GitHub)
```

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `python` no se reconoce o abre la Microsoft Store | Python no está en el PATH | Reinstalar marcando *Add python.exe to PATH* o desactivar los alias de la Store (paso 0) |
| `instalar.bat` falla en "Descargando el navegador Chromium" | Sin internet o proxy | Reintentar; o usar un Edge instalado con `CHROMIUM_PATH` en `.env` |
| La web dice "SIBIO-RFID no responde" y todo da **ERROR** | SIBIO apagado o `SIBIO_URL` incorrecta | Abrir `sibio-rfid\backend\iniciar.bat` y comprobar <http://127.0.0.1:5000> |
| Las E2E dan ERROR "el elemento … no apareció en el panel" | Falta compilar el panel de SIBIO | `cd sibio-rfid\frontend-v2` → `npm install` → `npm run build` y reiniciar SIBIO |
| "El administrador de pruebas no pudo entrar (HTTP 401)" | Clave de `admin` incorrecta | Revisar `SIBIO_ADMIN_CLAVE` en `.env` |
| "falta SIBIO_ADMIN_TOTP" o "debe vincular su app autenticadora" | El admin tiene (o debe tener) 2FA | Vincular el 2FA en SIBIO y copiar la clave manual a `SIBIO_ADMIN_TOTP` (paso 2.5) |
| "Esperando un código 2FA nuevo: N s" | SIBIO no acepta dos veces el mismo código | Es normal: la prueba espera el siguiente código (máximo 30 s) |
| La suite de seguridad bloquea el 2FA | TC-SEG-04 envía un código falso y SIBIO bloquea tras 5 fallos | No correr Seguridad más de 4 veces seguidas en 5 minutos |
| No llega el correo | SMTP sin configurar o contraseña normal en vez de *contraseña de aplicación* | Completar `SMTP_USUARIO`/`SMTP_CLAVE`; el informe igual queda para descargar en la web |
| La IA responde "simulado" o da error de clave | Sin `GEMINI_API_KEY` o clave inválida | Crear la clave en AI Studio o usar `IA_PROVEEDOR=simulado` |
| El dictado por voz no funciona | El navegador no trae reconocimiento de voz (por ejemplo, Brave) | Usar Microsoft Edge o Chrome |
| Puerto 8080 ocupado | Otro programa usa el puerto | Cambiar `QA_PUERTO` en `.env` |

> Solo se usan datos y usuarios ficticios del modo demostración. No se versionan `.env`, contraseñas reales, claves de API ni bases de datos.

## Autor

Marcos Alexander Panozo Patty · UNIFRANZ · TQA-711 · 02/2026
