import time
from odoo.api_wrapper import OdooAPIWrapper
from odoo.helpers import Table
from shared.config import ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD

def setup_helpdesk():
    odoo = OdooAPIWrapper(ODOO_BASE_URL, ODOO_USERNAME, ODOO_PASSWORD, ODOO_DB)

    # 2. Setup Teams
    teams = ["Presupuestos", "Soporte cliente"]
    print("Setting up Teams...")
    for t in teams:
        if not odoo.get_by_value(Table.TicketTeam, {'name': t}):
            team_id = odoo.create(Table.TicketTeam, [{'name': t}])
            print(f" [+] Created Team: {t} (ID: {team_id})")
        else:
            print(f" [~] Team {t} already exists.")

    # 3. Setup Ticket Types
    types = ["Presupuesto", "Soporte"]
    for ty in types:
        if not odoo.get_by_value(Table.TicketType, {'name': ty}):
            type_id = odoo.create(Table.TicketType, [{'name': ty}])
            print(f" [+] Created Type: {ty} (ID: {type_id})")
        else:
            print(f" [~] Type {ty} already exists.")

    # 4. Setup Categories
    categories = ["Consulta presupuesto", "Interno", "Problema"]
    print("\nSetting up Categories...")
    for c in categories:
        if not odoo.get_by_value(Table.TicketCategory, {'name': c}):
            cat_id = odoo.create(Table.TicketCategory, [{'name': c}])
            print(f" [+] Created Category: {c} (ID: {cat_id})")
        else:
            print(f" [~] Category {c} already exists.")

    # 5. Setup Stages
    stages = ["New", "In Progress", "Awaiting", "Done", "Cancelled", "Rejected"]
    print("\nSetting up Stages...")
    for s in stages:
        if not odoo.get_by_value(Table.TicketStage, {'name': s}):
            stage_id = odoo.create(Table.TicketStage, [{'name': s}])
            print(f" [+] Created Stage: {s} (ID: {stage_id})")
        else:
            print(f" [~] Stage {s} already exists.")

    # 6. Setup Tags
    tags = ["Urgente", "Cliente nuevo", "Pendiente validación", "Faltan datos"]
    print("\nSetting up Tags...")
    for tag in tags:
        # 'helpdesk.ticket.tag' isn't in Table enum, so we use the string directly
        if not odoo.get_by_value('helpdesk.ticket.tag', {'name': tag}):
            tag_id = odoo.create('helpdesk.ticket.tag', [{'name': tag}])
            print(f" [+] Created Tag: {tag} (ID: {tag_id})")
        else:
            print(f" [~] Tag {tag} already exists.")

    print("\nHelpdesk Setup Complete.")

if __name__ == "__main__":
    setup_helpdesk()
