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

    # Product (product.product) CRUD
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


# Examples / Tests -> this only executes if you run the file directly
if __name__ == '__main__':
    BASE_URL = 'http://localhost:8069/xmlrpc/2'
    db = 'odoo'
    username = 'senen.marques@live.u-tad.com'
    password = 'admin'

    try:
        odoo = OdooAPIWrapper(BASE_URL, username, password, db)
        print("Successfully connected to Odoo")

        # 1. Create a contact
        test_contact_data = {
            'name': 'Test Gemini Contact',
            'email': 'gemini@test.com',
            'is_company': False
        }
        contact_id = odoo.create_contact(test_contact_data)
        print(f"Created contact with ID: {contact_id}")

        # 2. Get the contact
        contact = odoo.get_contact(contact_id)
        if contact:
            print(f"Retrieved contact: {contact['name']} ({contact['email']})")

        # 3. Update the contact
        odoo.update_contact(contact_id, {'name': 'Updated Gemini Contact'})
        updated_contact = odoo.get_contact(contact_id)
        if updated_contact:
            print(f"Updated contact name: {updated_contact['name']}")

        # 4. List contacts
        contacts = odoo.get_contacts(limit=5)
        print(f"Retrieved {len(contacts)} contacts")
        for c in contacts:
            print(f" - {c['name']}")

        # 5. Delete the contact
        deleted = odoo.delete_contact(contact_id)
        print(f"Deleted contact: {deleted}")

        print("\n" + "="*20 + "\nTesting Products\n" + "="*20)

        # 1. Create a product
        test_product_data = {
            'name': 'Test Gemini Product',
            'list_price': 99.99,
            'description': 'A test product created by Gemini',
            'type': 'service'
        }
        product_id = odoo.create_product(test_product_data)
        print(f"Created product with ID: {product_id}")

        # 2. Get the product
        product = odoo.get_product(product_id)
        if product:
            print(f"Retrieved product: {product['display_name']} (Price: {product['list_price']})")

        # 3. Update the product
        odoo.update_product(product_id, {'list_price': 149.99})
        updated_product = odoo.get_product(product_id)
        if updated_product:
            print(f"Updated product price: {updated_product['list_price']}")

        # 4. List products
        products = odoo.get_products()
        print(f"Retrieved {len(products)} products")
        for p in products:
            print(f" - {p['display_name']}")

        # 5. Delete the product
        deleted = odoo.delete_product(product_id)
        print(f"Deleted product: {deleted}")

    except Exception as e:
        print(f"An error occurred: {e}")


