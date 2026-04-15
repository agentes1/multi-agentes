import time
from odoo.api_wrapper import OdooAPIWrapper
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

def setup_helpdesk():
    print(f"Connecting to Odoo at {ODOO_BASE_URL}...")
    odoo = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    # 1. Install Modules in the requested order
    modules = ['helpdesk_mgmt', 'helpdesk_type', 'helpdesk_motive']
    for module in modules:
        print(f"Installing {module}...")
        res = odoo.install_module(module)
        if res:
            print(f"Started installation of {module}.")
            time.sleep(10)  # Helpdesk modules can be heavy, give it some time
        else:
            print(f"Module {module} already installed or not found.")

    # 2. Setup Teams
    teams = ["Presupuestos", "Soporte cliente"]
    print("\nSetting up Teams...")
    for t in teams:
        if not odoo.search('helpdesk.ticket.team', [('name', '=', t)]):
            team_id = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'helpdesk.ticket.team', 'create', [{'name': t}])
            print(f" [+] Created Team: {t} (ID: {team_id})")
        else:
            print(f" [~] Team {t} already exists.")

    # 3. Setup Ticket Types (requires helpdesk_type)
    types = ["Presupuesto", "Soporte"]
    print("\nSetting up Ticket Types...")
    for ty in types:
        if not odoo.search('helpdesk.ticket.type', [('name', '=', ty)]):
            type_id = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'helpdesk.ticket.type', 'create', [{'name': ty}])
            print(f" [+] Created Type: {ty} (ID: {type_id})")
        else:
            print(f" [~] Type {ty} already exists.")

    # 4. Setup Categories
    categories = ["Consulta presupuesto", "Interno", "Problema"]
    print("\nSetting up Categories...")
    for c in categories:
        if not odoo.search('helpdesk.ticket.category', [('name', '=', c)]):
            cat_id = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'helpdesk.ticket.category', 'create', [{'name': c}])
            print(f" [+] Created Category: {c} (ID: {cat_id})")
        else:
            print(f" [~] Category {c} already exists.")

    # 5. Setup Stages
    stages = ["New", "In Progress", "Awaiting", "Done", "Cancelled", "Rejected"]
    print("\nSetting up Stages...")
    for s in stages:
        if not odoo.search('helpdesk.ticket.stage', [('name', '=', s)]):
            stage_id = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'helpdesk.ticket.stage', 'create', [{'name': s}])
            print(f" [+] Created Stage: {s} (ID: {stage_id})")
        else:
            print(f" [~] Stage {s} already exists.")

    # 6. Setup Tags
    tags = ["Urgente", "Cliente nuevo", "Pendiente validación", "Faltan datos"]
    print("\nSetting up Tags...")
    for tag in tags:
        if not odoo.search('helpdesk.ticket.tag', [('name', '=', tag)]):
            tag_id = odoo._models.execute_kw(ODOO_DB, odoo._uid, ODOO_PASSWORD, 'helpdesk.ticket.tag', 'create', [{'name': tag}])
            print(f" [+] Created Tag: {tag} (ID: {tag_id})")
        else:
            print(f" [~] Tag {tag} already exists.")

    print("\nHelpdesk Setup Complete.")

if __name__ == "__main__":
    setup_helpdesk()
