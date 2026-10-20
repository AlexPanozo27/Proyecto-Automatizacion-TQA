# Estrategia de automatización · SIBIO-RFID

| Nivel | Herramienta | Alcance |
|---|---|---|
| API | Python + requests (luego pytest) | Autenticación JWT, roles, CRUD de reclusos y usuarios, lecturas RFID, alertas |
| Interfaz | Playwright | Flujo de verificación (RFID → rostro → prueba de vida → huella) |
| Integración continua | GitHub Actions | Ejecutar la suite en cada push a `main` |

Criterios: cada caso automatizado proviene de un caso de prueba documentado (TC-xxx) en el repositorio Proyecto-Integrador-TQA, y cada fallo se registra como Issue con la etiqueta `bug`.
