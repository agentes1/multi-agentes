###
# El mail nos ayuda a ejecutar el agente sin llamar directamente a la función "adk run agente_prueba"
# Asi podemos ejecutar código y comprobar si se levanta cprrectamente el agente al recibir una petición
# Es una versión muy pobre, asi que si añadimos otras formas de meter datos tenemos que actualizarlo
###

from dotenv import load_dotenv
load_dotenv()

from adk.services.email_loader import load_test_email
from adk.services.agent_service import run_agent


def main():
    email = load_test_email()
    response = run_agent(email)

    print("\n----- EMAIL RECEIVED -----\n")
    print(email)

    print("\n----- AGENT RESPONSE -----\n")
    print(response)

if __name__ == "__main__":
    main()