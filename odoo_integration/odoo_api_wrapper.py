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

    def search(self, model, domain, limit=100):
        """Returns a list of IDs for records matching the domain."""
        return self._models.execute_kw(self._db, self._uid, self._password, model, 'search', [domain], {'limit': limit})

    def search_read(self, model, domain, fields=None, limit=100):
        """Returns a list of records matching the domain with specific fields."""
        params = {'limit': limit}
        if fields:
            params['fields'] = fields
        return self._models.execute_kw(self._db, self._uid, self._password, model, 'search_read', [domain], params)

    def drop_model(self, model):
        batch_limit = 1000
        while True:
            all_ids = self.search(model, [], limit=batch_limit)
            if not all_ids: break
            self._models.execute_kw(self._db, self._uid, self._password, model, 'unlink', [[all_ids]])
        return True
