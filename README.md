# Proyecto-Automatizacion-TQA

Repositorio del **proyecto de automatización** de la materia **TQA-711 · Pruebas y Aseguramiento de la Calidad de Software** (UNIFRANZ, 02/2026).

Almacena los **scripts, configuraciones y pruebas automatizadas** del sistema **SIBIO-RFID** (biometría facial, huella y manilla RFID).

## Estructura

```
tests/api/      Pruebas automatizadas contra la API REST (Python + requests)
config/         Configuración de ejemplo (URL de la API, base de datos de pruebas)
reportes/       Resultados y logs generados por cada ejecución
docs/           Estrategia de automatización
```

## Cómo ejecutar

1. Levantar SIBIO-RFID en modo demostración (SQLite + `datos_demo.py`).
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar variables (ver `config/config.example.env`).
4. Ejecutar: `python tests/api/ejecutar_pruebas_api.py`

El script ejecuta los casos de prueba del Entregable 1 (autenticación, usuarios, reclusos, manillas, alertas, eventos, reportes) y guarda un log HTTP por caso en `reportes/resultados/`.

> Solo se usan datos y usuarios ficticios del modo demostración. No se versionan `.env`, contraseñas reales ni bases de datos.

## Próximos pasos

- Convertir los casos a `pytest` con aserciones por paso.
- Pruebas de interfaz con Playwright.
- Ejecución automática en GitHub Actions en cada `push`.

## Autor

Marcos Alexander Panozo Patty · UNIFRANZ
