import xmlrpc.client

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

    def get_products(self):
        domain = [('active', '=', True)]
        return self._models.execute_kw(self._db, self._uid, self._password, 'product.product', 'search_read', [domain], {'limit': 10})

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


if __name__ == '__main__':
    BASE_URL = 'http://localhost:8069/xmlrpc/2'
    db = 'odoo'
    username = 'senen.marques@live.u-tad.com'
    password = 'admin'
    db_password = 'admin'

    odoo = OdooAPIWrapper(BASE_URL, username, password, db)
    # products = odoo.get_all('product.product')
    # [print(p['display_name']) for p in products]

    # res = odoo.get_products()
    res = odoo.get_product(15)
    if res:
        print(res.keys())

