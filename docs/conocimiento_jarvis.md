# Conocimiento del asistente Jarvis (QA Lab · SIBIO-RFID)

## Qué es cada cosa
- **SIBIO-RFID**: sistema bajo prueba. Control penitenciario: reclusos, manillas RFID con telemetría (pulso, contacto, batería), zonas y lectores, alertas, verificación biométrica (rostro + IA anti-suplantación MiniFASNet + prueba de vida con giros al azar + huella + manilla), varios penales, tiempo real (SSE), plano del penal en vivo, reportes, respaldos con simulacro de restauración. Backend Flask + Waitress, base PostgreSQL (SQLite en desarrollo), panel web React.
- **QA Lab**: la plataforma de automatización que prueba a SIBIO. No es SIBIO. Web Flask en el puerto 8080; SIBIO corre en el 5000.
- **Autor**: Alexander, estudiante de Ingeniería de Sistemas; proyecto de Testing y Aseguramiento de la Calidad (TQA). Defensa con el docente el 17/11/2026 (con retroalimentación) y versión final el 24/11/2026.

## Cómo funciona una ejecución (flujo)
1. En la web eliges tipo (funcional / no funcional), una suite o casos sueltos, tu correo y la velocidad del navegador.
2. El QA Lab crea un ID de ejecución (EJ-fecha-hora-XX) y lanza **pytest** en segundo plano.
3. Cada caso escribe sus pasos con lo observado; en E2E, **Playwright** controla Edge y toma una captura por paso. La web lee el avance cada 0,7 s y lo muestra en vivo.
4. Al terminar se calcula el resumen, la IA escribe el análisis de fallos, se genera el **informe PDF** (portada con dona, índice, conclusiones, detalle con capturas) y un **HTML** con la tabla resumen.
5. El **correo** se envía por **SMTP de Gmail** (STARTTLS, puerto 587) con los dos adjuntos. Usuario y contraseña de aplicación están en el archivo .env, nunca en el código ni en GitHub.

## Estados de un caso
- **PASS**: la verificación se cumplió.
- **FAIL**: fallo funcional: el sistema no hizo lo esperado (posible defecto de SIBIO).
- **ERROR**: no se pudo probar por el entorno (SIBIO apagado, navegador que no abre) o por el script (un elemento que ya no existe: se puede reparar con IA). No es culpa de SIBIO.
- **SKIPPED**: omitido a propósito (p. ej. TC-API-10 necesita el sensor de huella físico, fuera de alcance).
- **NOT RUN**: no llegó a ejecutarse (ejecución cancelada).
- Tasa de aprobación = PASS / (PASS + FAIL + ERROR).

## Tipos de prueba (definiciones simples)
- **Funcional**: ¿el sistema hace lo que debe? (login, registrar recluso, alerta por zona restringida).
- **No funcional**: ¿cómo lo hace? Rendimiento, carga, estrés, resistencia, seguridad.
- **Smoke (humo)**: lo mínimo esencial; si falla, no vale la pena seguir. Rápida.
- **Sanity (cordura)**: verificación rápida y enfocada después de un cambio puntual.
- **Regresión**: todo lo que ya funcionaba, para comprobar que un cambio nuevo no rompió nada.
- **Integración**: que los módulos funcionen juntos (lector RFID → API → alerta).
- **E2E (extremo a extremo)**: como un usuario real, en el navegador, de principio a fin.
- **Retesting**: volver a probar un defecto reportado para ver si ya se corrigió.
- **Rendimiento**: tiempos de respuesta con carga normal (p95 = el 95 % de las respuestas tarda menos que eso).
- **Estrés**: más carga de la normal, para ver dónde se degrada.
- **Soak (resistencia)**: carga sostenida en el tiempo, para ver si se degrada (fugas, lentitud progresiva).
- **Seguridad**: que los controles de protección funcionen (2FA, bloqueo, cadena de auditoría, inyección SQL, sesiones, datos sensibles).
- **Manual**: la hace una persona siguiendo pasos (M-01 a M-04 en el Capítulo 6).
- **Técnicas de diseño**: partición de equivalencia (grupos de datos que se comportan igual), valores límite (probar en el borde: 0, 100, 101), tabla de decisión (combinaciones de condiciones, como roles y permisos).

## Funciones de IA del QA Lab (Gemini)
- **Asistente IA**: caso en español → ambigüedades y supuestos → Gherkin → locators reales (mapa de 216 elementos leído del panel con Playwright) → código Playwright → revisión automática (sintaxis, nada peligroso, locators que existen) → aprobación humana → se guarda como TC-IA-NN y se ejecuta. La IA escribe; la ejecución real decide PASS o FAIL.
- **Análisis de fallos**: resumen en el informe y en la web.
- **Bug report con IA**: en un caso FAIL redacta el reporte de defecto (severidad, pasos, causa probable); ambiente, esperado y evidencia salen de la ejecución real.
- **Autocuración**: si un elemento del panel cambió de nombre, la IA elige el reemplazo solo entre los que existen hoy; el tester aprueba, se corrige el archivo (con copia) y se re-ejecuta. Demo: suite "Autocuración (demo IA)", TC-AC-01 ("Buscar internos" → "Buscar reclusos").
- **Modelo de respaldo**: si Gemini tarda más de 40 s o está saturado, responde un modelo más rápido y se avisa.
- **Jarvis** (este asistente): responde sobre el sistema, la teoría y los resultados reales; explica ejecuciones en lenguaje simple.
- **Jarvis ejecuta por orden:** si le escribes o dices "corre el Smoke" (o Regresión, E2E, Seguridad, etc.), prepara la suite, pide confirmación con el botón "Sí, ejecutar" y la lanza; la ejecución se ve en vivo en el centro de mando. Al terminar, Jarvis cuenta el resultado (y lo dice en voz alta si el 🔊 está activo). Esta orden se detecta sin IA: es instantánea y no gasta tokens.
- **Jarvis habla:** al abrirlo saluda con voz (por su nombre si le dices «llámame Marcos»), narra la ejecución en curso (cada caso y, en modo Presentación, cada paso) y al final dice si fue exitosa o qué falló. Si hubo errores, explica cada uno (FAIL = posible defecto de SIBIO; ERROR = falló la prueba o el entorno) y ofrece dos caminos: «Hazlo tú, Jarvis» (bug report con IA, reparar con IA, reintentar) o «Explícame cómo hacerlo yo». Si todo pasó, sugiere correr Regresión o Seguridad. Se calla con el botón 🔇 o diciendo «silencio», y vuelve con «habla».
- **Selector de modelo de Jarvis:** ⚡ Rápido (gemini-flash-lite, responde en pocos segundos), 🧠 Potente (gemini-3-flash, razona más pero tarda más) y 🔄 Auto (el del .env, que cambia solo al respaldo si el principal se satura). Debajo de cada respuesta se ve qué modelo contestó y en cuántos segundos. Elegir el modelo según la tarea es un equilibrio entre velocidad, costo y calidad.

## Otras funciones
- **Modo Presentación**: navegador más lento, rótulo del paso y resaltado naranja; capturas de evidencia limpias.
- **Espera del 2FA**: SIBIO no acepta dos veces el mismo código (anti-repetición); si ya se usó, la prueba espera el siguiente (hasta 30 s) y lo muestra.
- **Complementos**: Selenium WebDriver (2 casos de login con Edge) y Locust (carga con usuarios simultáneos, informe HTML).

## Resultados reales documentados (Capítulo 6, laptop, 17/11/2026, PostgreSQL)
- Smoke 5/5 PASS (35,6 s). Regresión 12 PASS, 1 FAIL controlado (TC-E2E-04, 32 alertas pendientes), 1 SKIPPED (80,6 s).
- Rendimiento p95 220 ms, 0 errores. Estrés 500 peticiones, 0 errores, p95 976 ms. Soak: mediana 128 → 172 ms.
- Selenium 2/2. Locust 1641 peticiones, 0 errores, p95 260 ms, 14 req/s.
- Retesting 5 FAIL: BUG-001 (CI acepta letras), BUG-003 (UID RFID corto), BUG-005 (batería 250 %) abiertos; BUG-002 parcial (fecha futura aceptada); BUG-004 (bpm 'abc' da HTTP 500) sigue; BUG-006 parcial (PDF sí, Excel no).
- Pruebas manuales M-01 a M-04: PASS.
- Cobertura de automatización 9/12 = 75 % (faltan TC-008, TC-012, TC-014); cobertura de requisitos 11/11.

## Seguridad que implementa SIBIO
2FA obligatoria para administradores; bloqueo tras 5 contraseñas (5 min); auditoría encadenada HMAC-SHA256 con ancla externa y verificación periódica (alerta crítica si se altera); datos sensibles cifrados con AES; sesiones JWT con identificador que se invalidan al salir o al cambiar la clave; permisos por rol y por penal; bloqueo de pantalla por inactividad; HTTPS con Caddy.

## Tecnologías y por qué
- **SIBIO-RFID backend**: **Python** con **Flask** (API REST), servido en producción con **Waitress** (32 hilos). Base de datos **PostgreSQL** (en desarrollo, SQLite). Librerías clave: PyJWT (sesiones), cryptography (AES-256-GCM), OpenCV (YuNet detecta el rostro, SFace lo compara), psycopg2 (PostgreSQL).
- **SIBIO-RFID frontend**: panel nuevo en **React 18 + TypeScript** con **Vite**; el panel antiguo es HTML + JavaScript. Tiempo real con **SSE** (el servidor empuja las alertas al navegador en ~76 ms, sin recargar).
- **QA Lab (esta automatización)**: **Python** con **pytest** (motor de pruebas y suites por marcas), **Playwright** (controla Edge para E2E y saca capturas), **requests** (pruebas de API), **Selenium** (complemento, 2 casos), **Locust** (carga con usuarios simultáneos), **Flask + Waitress** (la web del QA Lab), **Jinja2** (plantillas del informe), SMTP de Gmail (correo) y **Gemini** de Google (IA).
- **¿Por qué Python?** Es el mismo lenguaje del backend de SIBIO (se reutiliza conocimiento y se puede leer su código), pytest es el estándar de pruebas en Python con marcas, fixtures y plugins, y Playwright tiene API oficial en Python. **¿Por qué Playwright y no solo Selenium?** Espera solo a que los elementos estén listos (menos pruebas inestables), localiza por rol y texto visible como un usuario, saca capturas fácilmente y es más rápido; Selenium se incluye como complemento para comparar.

## APIs de SIBIO (134 operaciones en 115 rutas, 19 grupos; REST, JSON, con token JWT; documentación Swagger en /api/docs, funciona sin internet)
/api/auth (login, 2FA, salir, opciones), /api/usuarios, /api/reclusos (ficha, fotos, búsqueda), /api/manillas (manillas RFID y telemetría), /api/dispositivos y /api/puntos-control (lectores), zonas, /api/eventos (lecturas RFID), /api/alertas, /api/reportes, /api/respaldos (y simulacro de restauración), biometría (verificación de rostro, prueba de vida, huella), expediente, ingreso, recintos (varios penales), panel (indicadores) y /api/auditoria (incluye /integridad para verificar la cadena). El QA Lab prueba 15 casos de API directamente.

## Puntos fuertes de SIBIO-RFID (para la defensa)
Varios penales con aislamiento de datos (un usuario de un penal no ve otro: responde 404); alertas en tiempo real por SSE; verificación biométrica en capas (rostro + anti-suplantación con IA + prueba de vida con giros al azar + huella + manilla); manillas RFID con telemetría (pulso, contacto con la piel, batería) que genera alertas; plano del penal en vivo; auditoría a prueba de manipulación (cadena HMAC-SHA256); datos biométricos cifrados (AES-256-GCM); 2FA para administradores; respaldos con simulacro de restauración; reportes; documentación de la API; detección de duplicados 1:N al registrar (un mismo rostro con dos identidades); prueba de vida alineada con ISO/IEC 30107-3 (detección de ataques de presentación); acta de ingreso sellada con credencial QR; expediente y ficha médica; recuentos; escalamiento de alertas críticas por correo a los administradores; huella con sensor R307/AS608 preparada (modo simulado hasta comprar el sensor); y un QA Lab propio que lo prueba todo de forma automática con IA.

## Seguridad explicada simple
- **Contraseñas**: nunca se guardan tal cual, se guarda un hash PBKDF2 (miles de vueltas de SHA-256 con sal); ni el administrador puede leerlas.
- **2FA (doble factor)**: además de la contraseña, un código de 6 dígitos de una app autenticadora (Google o Microsoft Authenticator). Usa el estándar **TOTP** (RFC 6238): el servidor y el celular comparten un secreto y cada 30 segundos calculan el mismo código con la hora. No necesita internet en el celular. Un código usado no se acepta dos veces (anti-repetición). Hay códigos de recuperación.
- **SHA-256**: una "huella digital" de un texto o archivo: siempre 64 caracteres hexadecimales; si cambia una sola letra, el resultado cambia por completo, y no se puede volver atrás para obtener el original.
- **HMAC-SHA256**: SHA-256 mezclado con una clave secreta del servidor; así, alguien que cambie un dato no puede recalcular el sello sin la clave.
- **Cadena de auditoría**: cada registro lleva un sello HMAC-SHA256 de su contenido MÁS el sello del registro anterior, como eslabones. Si alguien borra o cambia un registro por fuera del sistema (por ejemplo desde pgAdmin), la cadena se rompe en ese punto, la verificación lo detecta y se genera una alerta crítica. La suite Seguridad del QA Lab lo comprueba (TC-SEG-01).
- **AES-256-GCM**: cifrado de los datos biométricos guardados (rostros, huellas): sin la clave son ilegibles, y GCM además detecta si alguien los alteró.
- **JWT**: el "pase" de sesión firmado; se invalida al salir o al cambiar la clave (TC-SEG-06 lo prueba).
- **HTTPS (TLS)** con Caddy: cifra la comunicación entre el navegador y el servidor; necesario para usar la cámara en otras PC.
- **Ojo con "E2E"**: en este proyecto E2E significa **pruebas de extremo a extremo** (un usuario simulado en el navegador), no "cifrado de extremo a extremo". SIBIO cifra en tránsito con HTTPS y en reposo con AES.
- **Otras defensas probadas**: bloqueo tras 5 contraseñas fallidas (HTTP 429), consultas parametrizadas contra inyección SQL, respuestas sin datos sensibles ni trazas de error, permisos por rol y por penal.

## Métricas de calidad del QA Lab (pestaña "Métricas")
- **Salud de la versión**: el % de éxito de la última ejecución, en colores (verde alto, ámbar medio, rojo bajo).
- **Tasa de éxito global**: PASS / casos ejecutados, sumando todo el historial.
- **Ejecuciones**: cuántas corridas terminadas hay y cuántos casos sumaron.
- **Fallos funcionales vs errores de infraestructura**: FAIL apunta a defectos de SIBIO; ERROR a problemas del entorno o del script. Separarlos evita culpar al sistema por un fallo de la prueba.
- **Duración media** por ejecución, **tendencia** de las últimas 20 (barras por estado y línea de % de éxito) y **casos que más fallan** (dónde concentrar la corrección).
- **Otras métricas del Capítulo 6**: cobertura de automatización 9/12 = 75 %; cobertura de requisitos 11/11; defectos encontrados por el retesting (BUG-001 a 006); rendimiento con p95 (el 95 % de las respuestas tarda menos que ese valor), errores y peticiones por segundo.

## Ideas a futuro (sugerencias, no implementadas)
Generador de casos límite con IA; automatizar TC-008/012/014 (100 %); corregir BUG-001 a 005 y repetir el retesting; revisión visual con IA de las capturas; video de cada E2E; comparar dos ejecuciones; priorización por riesgo; lanzar Selenium y Locust desde la web; ejecutar en CI de GitHub; pruebas de accesibilidad; despliegue en la nube.
