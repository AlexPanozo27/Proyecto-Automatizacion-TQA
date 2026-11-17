"""Caso TC-IA-01 generado con IA (gemini) y revisado antes de ejecutarse."""
from playwright.sync_api import expect  # noqa: F401

from ayudas_e2e import entrar, ir_a  # noqa: F401
from soporte import caso


@caso('TC-IA-01', '[IA] Verificación de existencia de usuario jperez en Usuarios y roles', suites=["e2e", "ia"],
      modulo='Usuarios y roles', objetivo="Validar que el usuario con identificador 'jperez' se encuentra correctamente listado en el módulo de gestión de usuarios.", precondiciones="El administrador debe haber iniciado sesión y el usuario 'jperez' debe estar previamente registrado en el sistema.",
      datos="Usuario a buscar: 'jperez'", resultado_esperado="El sistema muestra al usuario 'jperez' dentro de la tabla de resultados del módulo Usuarios y roles.")
def test_ia_01(pagina, registro):
    # Caso escrito por el usuario:
    # El administrador abre Usuarios y roles y verifica que el usuario jperez aparece en la lista.
    # Gherkin generado:
    # Característica: Gestión de usuarios y roles
    # 
    #   Escenario: Verificar la presencia de un usuario en el listado
    #     Dado que el administrador ha iniciado sesión en el panel SIBIO-RFID
    #     Cuando accede al módulo "Usuarios y roles"
    #     Y visualiza la lista de usuarios registrados
    #     Entonces el sistema debe mostrar al usuario "jperez" en la lista de resultados
    entrar(pagina, registro, "administrador")
    ir_a(pagina, registro, "Usuarios y roles")
    with registro.paso("Buscar al usuario 'jperez' en el listado") as p:
        buscador = pagina.get_by_placeholder("Nombre, usuario o penal…")
        buscador.fill("jperez")
        buscador.press("Enter")
        p["observado"] = "Se ingresó 'jperez' en el campo de búsqueda de usuarios"
    with registro.paso("Verificar que el usuario 'jperez' es visible") as p:
        # Se utiliza el locator del combobox de rol específico para este usuario según el mapa
        expect(pagina.get_by_role("combobox", name="Rol de jperez")).to_be_visible()
        p["observado"] = "El sistema muestra al usuario 'jperez' en la tabla de resultados"
