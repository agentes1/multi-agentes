import xmlrpc.client

# Usage Examples can be found in tests.test_odoo_api_wrapper
# Credentials can be found in shared/config

class OdooAPIWrapper:
    def __init__(self, url, username, password, db):
        self._url = url if 'xmlrpc/2' in url else self._format(url)
        self._username = username
        self._password = password
        self._db = db
        self._uid = self._login()
        self._models = xmlrpc.client.ServerProxy(f'{self._url}/object')

    def _format(self, url):
        pieces = url.split(':')
        pieces[2] = pieces[2][:4] # just the port
        return f'{':'.join(pieces[:3])}/xmlrpc/2'

    def _login(self):
        common = xmlrpc.client.ServerProxy(f'{self._url}/common')
        uid = common.authenticate(self._db, self._username, self._password, {})
        if not uid: raise RuntimeError('URL was correct, but credentials were wrong, don\'t give up ur close!')
        return uid

    def get_dbs(self):
        try:
            client = xmlrpc.client.ServerProxy(f'{self._url}/db')
            dbs = client.list()
            print("Databases available in Odoo:", dbs)
        except Exception as e:
            print("Could not list DBs:", e)

    def get_all(self, tablename, limit=100):
        return self._models.execute_kw(self._db, self._uid, self._password, tablename, 'search_read', [], {'limit': limit})

    # Product (product.product) CRUD
    def get_products(self, limit=10):
        domain = [('active', '=', True)]
        return self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'search_read', [domain], {'limit': limit})

    def create_product(self, data):
        return self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'create', [data])

    def get_product(self, product_id):
        result = self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'read', [[product_id]])
        return result[0] if result else None

    def update_product(self, product_id, data):
        return self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'write', [[product_id], data])

    def delete_product(self, product_id):
        return self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'unlink', [[product_id]])

    # Contact (res.partner) CRUD
    def get_contacts(self, limit=10):
        domain = [('active', '=', True)]
        return self._models.execute_kw(self._db, self._uid, self._password, 'res.partner', 'search_read', [domain], {'limit': limit})

    def create_contact(self, data):
        return self._models.execute_kw(self._db, self._uid, self._password, 'res.partner', 'create', [data])

    def get_contact(self, contact_id):
        result = self._models.execute_kw(self._db, self._uid, self._password, 'res.partner', 'read', [[contact_id]])
        return result[0] if result else None

    def update_contact(self, contact_id, data):
        return self._models.execute_kw(self._db, self._uid, self._password, 'res.partner', 'write', [[contact_id], data])

    def delete_contact(self, contact_id):
        return self._models.execute_kw(self._db, self._uid, self._password, 'res.partner', 'unlink', [[contact_id]])

    # miscellaneous
    def install_module(self, module_name):
        module_ids = self.search('ir.module.module', [('name', '=', module_name)])
        if module_ids:
            return self._models.execute_kw(self._db, self._uid, self._password, 'ir.module.module', 'button_immediate_install', [module_ids])
        return False

    def update_module_list(self):
        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'ir.module.module',
            'update_list',
            [],
        )

    def search(self, model, domain, limit=100):
        """Returns a list of IDs for records matching the domain."""
        return self._models.execute_kw(self._db, self._uid, self._password, model, 'search', [domain], {'limit': limit})

    def search_read(self, model, domain, fields=None, limit=100):
        """Returns a list of records matching the domain with specific fields."""
        params = {'limit': limit}
        if fields:
            params['fields'] = fields
        return self._models.execute_kw(self._db, self._uid, self._password, model, 'search_read', [domain], params)

    def get_model_fields(self, model):
        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            model,
            'fields_get',
            [],
            {'attributes': ['string', 'type']},
        )

    def drop_model(self, model):
        batch_limit = 1000
        while True:
            all_ids = self.search(model, [], limit=batch_limit)
            if not all_ids: break
            self._models.execute_kw(self._db, self._uid, self._password, model, 'unlink', [[all_ids]])
        return True


# helpers helpdesk
    # obtiene el id de un equipo por nombre exacto
    def get_team_id_by_name(self, team_name):
        team_ids = self.search(
            'helpdesk.ticket.team',
            [('name', '=', team_name)],
            limit=1,
        )
        return team_ids[0] if team_ids else None

    # obtiene el id de un tipo de ticket por nombre exacto
    def get_ticket_type_id_by_name(self, type_name):
        type_ids = self.search(
            'helpdesk.ticket.type',
            [('name', '=', type_name)],
            limit=1,
        )
        return type_ids[0] if type_ids else None

    # obtiene el id de una categoría por nombre exacto
    def get_category_id_by_name(self, category_name):
        category_ids = self.search(
            'helpdesk.ticket.category',
            [('name', '=', category_name)],
            limit=1,
        )
        return category_ids[0] if category_ids else None

    # obtiene los ids de las etiquetas que existan en Odoo
    # si una etiqueta no existe simplemente no se devuelve
    def get_tag_ids_by_names(self, tag_names):
        if not tag_names:
            return []

        return self.search(
            'helpdesk.ticket.tag',
            [('name', 'in', tag_names)],
            limit=100,
        )

    # obtiene el motivo si existe y pertenece al equipo indicado
    # se deja como helper opcional porque todavía no has definido motivos
    def get_motive_id_by_name_and_team(self, motive_name, team_id):
        motive_ids = self.search(
            'helpdesk.ticket.motive',
            [('name', '=', motive_name), ('team_id', '=', team_id)],
            limit=1,
        )
        return motive_ids[0] if motive_ids else None

    # crea un ticket real en el modelo helpdesk.ticket
    # se mantiene simple: solo campos necesarios para tu flujo local
    def create_helpdesk_ticket(
        self,
        title,
        description,
        team_id,
        priority="1",
        type_id=None,
        category_id=None,
        tag_ids=None,
        motive_id=None,
    ):
        vals = {
            'name': title,
            'description': description,
            'team_id': team_id,
            'priority': priority,
        }

        # campos opcionales: solo se añaden si existen
        if type_id:
            vals['type_id'] = type_id

        if category_id:
            vals['category_id'] = category_id

        if motive_id:
            vals['motive_id'] = motive_id

        # relación many2many con etiquetas
        if tag_ids:
            vals['tag_ids'] = [(6, 0, tag_ids)]

        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'helpdesk.ticket',
            'create',
            [vals],
        )
    
    def get_helpdesk_ticket(self, ticket_id):
        result = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            "helpdesk.ticket",
            "read",
            [[ticket_id]],
        )
        return result[0] if result else None
    
    def get_helpdesk_tickets(self, limit: int = 100):
        ids = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            "helpdesk.ticket",
            "search",
            [[]],
            {"limit": limit},
        )
        if not ids:
            return []

        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            "helpdesk.ticket",
            "read",
            [ids],
        )

    def find_company(self, name, exact=False, limit=5):
        operator = '=ilike' if exact else 'ilike'
        return self.search_read(
            'res.partner',
            [('is_company', '=', True), ('name', operator, name)],
            fields=['id', 'name', 'email', 'is_company'],
            limit=limit,
        )

    def find_client(self, name):
        clients = self.search_read(
            'res.partner',
            [('name', 'ilike', name), ('active', '=', True)],
            fields=['id', 'name', 'email', 'phone', 'is_company'],
            limit=1,
        )
        return clients[0] if clients else None
    
    # helpers presupuesto / ventas

    def get_or_create_contact(self, company_name):
        partners = self.search_read(
            'res.partner',
            [('name', '=', company_name)],
            fields=['id', 'name'],
            limit=1,
        )
        if partners:
            return partners[0]['id']
        return self.create_contact({'name': company_name, 'company_type': 'company'})

    def get_product_by_code(self, product_code):
        products = self.search_read(
            'product.product',
            [('default_code', '=', product_code)],
            fields=['id', 'name', 'default_code', 'lst_price'],
            limit=1,
        )
        return products[0] if products else None

    def create_sale_order(self, partner_id):
        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'sale.order',
            'create',
            [{'partner_id': partner_id}],
        )

    def create_sale_order_line(self, order_id, product_id, quantity=1):
        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'sale.order.line',
            'create',
            [{
                'order_id': order_id,
                'product_id': product_id,
                'product_uom_qty': quantity,
            }],
        )

    def get_sale_order(self, order_id):
        result = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'sale.order',
            'read',
            [[order_id]],
        )
        return result[0] if result else None

    def get_order(self, order_id):
        result = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'sale.order',
            'read',
            [[order_id]],
            {'fields': ['name', 'state', 'amount_untaxed', 'amount_total', 'date_order']},
        )
        return result[0] if result else None

    def get_sale_order_lines(self, order_id):
        lines = self.search_read(
            'sale.order.line',
            [('order_id', '=', order_id)],
            fields=[
                'name',
                'product_id',
                'product_uom_qty',
                'price_unit',
                'price_subtotal',
            ],
            limit=100,
        )

        # añadimos default_code del producto para mantener coherencia con QuoteLine
        enriched = []
        for line in lines:
            product_data = None
            product_field = line.get('product_id')
            if product_field and isinstance(product_field, list):
                product_id = product_field[0]
                product = self.get_product(product_id)
                product_data = product

            enriched.append({
                'name': line.get('name', ''),
                'product_uom_qty': line.get('product_uom_qty', 1),
                'price_unit': line.get('price_unit', 0),
                'price_subtotal': line.get('price_subtotal', 0),
                'default_code': product_data.get('default_code', '') if product_data else '',
            })

        return enriched
    
    def find_products_by_text(self, text, limit=20):
        text = str(text).strip()
        if not text:
            return []

        return self.search_read(
            'product.product',
            [
                '|',
                ('name', 'ilike', text),
                ('default_code', 'ilike', text),
            ],
            fields=['id', 'name', 'default_code', 'lst_price'],
            limit=limit,
        )

    def list_catalog(self, limit=100):
        return self.search_read(
            'product.product',
            [('active', '=', True)],
            fields=['id', 'name', 'default_code', 'lst_price', 'description'],
            limit=limit,
        )

    def list_client_orders(self, partner_id, limit=10):
        return self.search_read(
            'sale.order',
            [('partner_id', '=', partner_id)],
            fields=['id', 'name', 'state', 'amount_total', 'date_order'],
            limit=limit,
        )

    def list_client_tickets(self, partner_id, limit=10):
        return self.search_read(
            'helpdesk.ticket',
            [('partner_id', '=', partner_id)],
            fields=['id', 'name', 'stage_id', 'team_id'],
            limit=limit,
        )

    def get_client_history(self, partner_id, limit=10):
        return {
            'orders': self.list_client_orders(partner_id, limit=limit),
            'tickets': self.list_client_tickets(partner_id, limit=limit),
        }

    # helpers discuss / chat bot

    def get_user_by_login(self, login):
        users = self.search_read(
            'res.users',
            [('login', '=', login)],
            fields=['id', 'login', 'partner_id', 'name'],
            limit=1,
        )
        return users[0] if users else None

    def get_user_by_name(self, name):
        users = self.search_read(
            'res.users',
            [('name', '=', name)],
            fields=['id', 'login', 'partner_id', 'name'],
            limit=1,
        )
        return users[0] if users else None

    def create_user(self, data):
        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'res.users',
            'create',
            [data],
        )

    def get_or_create_internal_user(self, login, name, email=None):
        user = self.get_user_by_login(login)
        if user:
            return user

        user = self.get_user_by_name(name)
        if user:
            return user

        partner_email = email or login
        partner = self.get_partner_by_email(partner_email)
        if partner:
            partner_id = partner['id']
        else:
            partner_id = self.create_contact(
                {
                    'name': name,
                    'email': partner_email,
                    'company_type': 'person',
                }
            )

        user_id = self.create_user(
            {
                'name': name,
                'login': login,
                'partner_id': partner_id,
                'email': partner_email,
            }
        )
        return self.search_read(
            'res.users',
            [('id', '=', user_id)],
            fields=['id', 'login', 'partner_id', 'name'],
            limit=1,
        )[0]

    def set_system_parameter(self, key, value):
        existing = self.search_read(
            'ir.config_parameter',
            [('key', '=', key)],
            fields=['id', 'key', 'value'],
            limit=1,
        )
        if existing:
            self._models.execute_kw(
                self._db,
                self._uid,
                self._password,
                'ir.config_parameter',
                'write',
                [[existing[0]['id']], {'value': value}],
            )
            return existing[0]['id']

        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'ir.config_parameter',
            'create',
            [{'key': key, 'value': value}],
        )

    def get_partner_by_email(self, email):
        partners = self.search_read(
            'res.partner',
            [('email', '=', email)],
            fields=['id', 'name', 'email'],
            limit=1,
        )
        return partners[0] if partners else None

    def get_or_create_discuss_bot_user(self, login='assistant.bot', name='Assistant Chatbot'):
        user = self.get_user_by_login(login)
        if user:
            return user

        partner_id = self.create_contact({'name': name, 'email': login, 'company_type': 'person'})
        user_id = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'res.users',
            'create',
            [{
                'name': name,
                'login': login,
                'partner_id': partner_id,
            }],
        )
        return self.search_read(
            'res.users',
            [('id', '=', user_id)],
            fields=['id', 'login', 'partner_id', 'name'],
            limit=1,
        )[0]

    def open_direct_chat(self, partner_ids, channel_name):
        existing = self.search_read(
            'mail.channel',
            [('name', '=', channel_name)],
            fields=['id', 'name'],
            limit=1,
        )
        if existing:
            return existing[0]

        channel_id = self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'mail.channel',
            'create',
            [{
                'name': channel_name,
                'channel_type': 'chat',
                'channel_partner_ids': [(6, 0, partner_ids)],
            }],
        )
        return {'id': channel_id, 'name': channel_name}

    def post_message_to_channel(self, channel_id, body, author_id=None):
        vals = {
            'body': body,
            'message_type': 'comment',
            'model': 'mail.channel',
            'res_id': channel_id,
        }
        if author_id:
            vals['author_id'] = author_id

        return self._models.execute_kw(
            self._db,
            self._uid,
            self._password,
            'mail.message',
            'create',
            [vals],
        )
