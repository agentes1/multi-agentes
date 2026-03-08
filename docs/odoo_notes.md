# ODOO NOTES

## Documentation Links
- [SETUP GUIDE](https://www.odoo.com/documentation/master/developer/tutorials/setup_guide.html)
- [ODOO-BIN ARGUMENTS](https://www.odoo.com/documentation/master/developer/reference/cli.html#reference-cmdline-server)
- [Python Debugging](https://www.odoo.com/documentation/master/developer/tutorials/setup_guide.html#python-debugging)
- [Odoo Architecture (learn how to make odoo modules)](https://www.odoo.com/documentation/master/developer/tutorials/server_framework_101.html)
- [ODOO ORM API](https://www.odoo.com/documentation/master/developer/reference/backend/orm.html#orm-api)

## INSTALL ODOO:
```bash mkdir odoos && cd odoos
git clone https://github.com/odoo/odoo.git
git clone https://github.com/odoo/tutorials.git
python3.12 -m venv odoo-env
source odoo-env/bin/activate
pip install --upgrade --force-reinstall -r requirements.txt

```
[SETUP GUIDE](https://www.odoo.com/documentation/master/developer/tutorials/setup_guide.html)

## LAUNCH ODOO SERVER
```bash
./odoo-bin -d <database> --addons-path <directories> --limit-time-cpu <limit> --limit-time-real <limit>
./odoo-bin -d rd-demo --addonts-path="../tutorials" # -u estate (update a module named estate)
```

[ODOO-BIN ARGUMENTS](https://www.odoo.com/documentation/master/developer/reference/cli.html#reference-cmdline-server)

## Log In as admin

- `http://localhost:8069`
- With Debug mode: `http://localhost:8069?debug=1` or `CTRL+K -> activate Debug Mode`
- email: `admin`
- password: `admin`

## Misc
- View the DB Structure through the UI in `Settings > Technical > Database Structure > Models`
- `http://localhost:8069/odoo/discuss` opens a chatbot
- [Python Debugging](https://www.odoo.com/documentation/master/developer/tutorials/setup_guide.html#python-debugging)
- [Odoo Architecture (learn how to make odoo modules)](https://www.odoo.com/documentation/master/developer/tutorials/server_framework_101.html)

## Odoo Architecture

- 3 Layer Architecture:
  - Presentation Tier (HTML, CSS, JS) (although it is transitioning to use [In-House Framework](https://odoo.github.io/owl/)
  - Logic Tier (Python)
  - Data Tier (PostgreSQL as RDBMS)
- __Modules__ user facing modules aka __Apps__, not all modules are Apps
- Modules are loaded with the `--addons-path` argument
- Simplified Module Directory:
```
module
├── models
│   ├── *.py
│   └── __init__.py
├── data
│   └── *.xml
├── __init__.py
└── __manifest__.py
```
- `__manifest.py__` file contains module metadata
```python
{
    'name': "A Module",
    'version': '1.0',
    'depends': ['base'],
    'author': "Author Name",
    'category': 'Category',
    'installable': True,
    'application': True, # AKA user facing module
    'description': """
    Description text
    """,
    # data files always loaded at installation
    'data': [
        'views/mymodule_view.xml',
    ],
    # data files containing optionally loaded demonstration data
    'demo': [
        'demo/demo_data.xml',
    ],
}
```



## Installing / Updating Modules
```bash
./odoo-bin --addons-path=addons,../tutorials -d rd-demo -i estate
```
The estate module lives inside tutorials, you import the addons (paths containing modules), and make sure to use the `-i` flag.
After using the `-i` flag, which supposedly creates the necesary tables in `psql` you can continue updating the module with the `-u` flag
```bash
./odoo-bin --addons-path=addons,../tutorials -d rd-demo -u estate
```
Verify in database:
```bash
psql -d rd-demo
select * from table_name;
\d table_name
```

[ODOO ORM API](https://www.odoo.com/documentation/master/developer/reference/backend/orm.html#orm-api)

## Module Data Directories
Data directories in modules follow a naming convention
- `models` ORM stuff, define tables with fields 
- `data` files importing data
- `security` data related to security 
- `views` when data is related to views and actions

Additionally, all these files must be declared in the `data` list within the module's `__manifest__.py` 

## How is a Module's Data Loaded?
Take this example:
```python
# INSIDE __manifest__.py
'data': [
    'data/res.lang.csv',
    'data/res_lang_data.xml',
    'data/res_partner_data.xml',
    'data/res_company_data.xml',
    'security/ir.model.access.csv', # important to know, access rights go here
]
```

- The data files are sequentially loaded following their order in the __manifest__.py file. This means that if data A refers to data B, you must make sure that B is loaded before A.
- All the security configuration of a model is loaded through data files

## Access Rights
Access rights are defined as records of the model `ir.model.access` (MODEL AKA DB TABLE, NOT TO BE CONFUSED WITH MODULE)
Access rights are defined in `ir.model.access.csv`

Example of access rights for a single model:
```csv
id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink
access_test_model,access_test_model,model_test_model,base.group_user,1,0,0,0
```
For clarification, see [Access Rights](https://www.odoo.com/documentation/master/developer/tutorials/server_framework_101/04_securityintro.html)


## Module's UI
After creating the model and its corresponding access rights, we can move onto UI

### Actions
An action can be viewed as the link between the __menu__ and the __model__
Here we have our `estate/views/estate_property_views.xml`
We must update the `data` list in `__manifest__.py` with `views/estate_property_views.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <record id="estate_property_action" model="ir.actions.act_window"> <!-- id is an identifier -->
        <field name="name">Estate Action</field>
        <field name="res_model">estate.property</field> <!-- the model -->
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

### Menus
Model <-> Action <-> Menu


Odoo cuenta con un framework completo que cubre ya tanto la capa de datos como la interfaz 
    permite definir tablas y triggers mediante un ORM
    y definir acciones y menus mediante xml 
    en resumen permite hacer mucho con pocas lineas de codigo
Y tambien cuenta con documentacion exhaustiva.
Estamos investigandolo para poder integrarlo en nuestro projecto

papers para hacer sistemas multiagente, (eg microsoft)
mirar framework de agentes que vamos a usar
protocolos de comunicacion de agentes
la confianza es muy complicada -> no es analisis de sentimientos, es clasificacion de la tarea
\-> mejor usar un modelo de clasificacion


agentes tienen tools, reflextion and multistep
ver flujos de agentes q se comunican entre si para ver resultado final

si agente habla con cliente q ha hablado mucho, mejor ir al rag?

usar vllm, sglang, en vez de ollama
usar tai para optimizar los embeddings

