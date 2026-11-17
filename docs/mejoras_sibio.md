# Mejoras propuestas (para cuando pidan sugerencias; di siempre que son PROPUESTAS, no cosas hechas)

## Contexto
SIBIO-RFID es el proyecto de grado de Alexander: control de reclusos para el Régimen Penitenciario de Bolivia (penales de La Paz como San Pedro y Chonchocoro; meta a futuro: uso nacional por la DGRP). Por eso importan la trazabilidad, la seguridad, que funcione sin internet en el penal y la facilidad de uso para el personal.

## Para SIBIO (con su motivo real)
1. **Validaciones en el backend** (cierra BUG-001, 003 y 005): CI solo con números y formato boliviano, UID RFID con largo fijo, batería entre 0 y 100 %. Hoy el retesting las sigue encontrando abiertas.
2. **Errores 400 en vez de 500** (BUG-004): si el pulso llega como 'abc', responder 400 "dato inválido" y no un error interno.
3. **Fechas futuras rechazadas** (BUG-002 parcial) y **exportación a Excel** (BUG-006 parcial).
4. **Rendimiento de la búsqueda**: el p95 sube a 976 ms en estrés (220 ms normal); índices en PostgreSQL (CI, nombre, UID) y caché corta del panel.
5. **HTTPS en la red del penal** con Caddy (ya preparado, falta instalarlo) y rotar las claves del .env.
6. **Hardware real**: sensor de huella R307 (código listo, falta comprarlo) y manilla física con MQTT.
7. **Despliegue**: servidor por penal con réplica central, respaldos automáticos fuera del equipo, monitoreo.
8. **Alertas**: aviso por WhatsApp o SMS además del correo; app móvil para guardias.

## Para la automatización (QA Lab)
1. **Cobertura 75 % → 100 %**: automatizar TC-008, TC-012 y TC-014.
2. **Generador de casos límite con IA** a partir de los bugs (valores límite y partición de equivalencia).
3. **Integración continua**: correr Smoke y Regresión solos en GitHub Actions en cada cambio.
4. **Comparar dos ejecuciones** y revisión visual con IA de las capturas (detectar cambios de diseño).
5. **Video de cada E2E**, pruebas de accesibilidad y de varios navegadores.
6. **Seguridad avanzada**: escaneo con OWASP ZAP y prueba de permisos por rol en cada ruta de la API (la documentación OpenAPI permite generarlas solas).
7. **Dictado por voz que funcione en cualquier navegador** (Gemini transcribe el audio) y lanzar Selenium y Locust desde la web.
