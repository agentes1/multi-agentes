###
# En los servicios definimos algunas funciones que nos ayudan a gestionar al agente
# Este servicio nos ayuda a extraer un JSON para realizar pruebas
# El servicio lee un archivo, y devuelve un JSON
###

import json

def load_test_email():
    with open("adk/test_data/test.json", "r") as f: 
        return json.load(f)