import os
import xmlrpc.client


class OdooNotifier:
    def __init__(self):
        base_url = os.getenv("ODOO_BASE_URL", "http://localhost:8069/xmlrpc/2")
        self.db = os.getenv("ODOO_DB")
        self.username = os.getenv("ODOO_USERNAME")
        self.password = os.getenv("ODOO_PASSWORD")

        common_url = base_url.replace("/xmlrpc/2", "/xmlrpc/2/common")
        object_url = base_url.replace("/xmlrpc/2", "/xmlrpc/2/object")

        self.common = xmlrpc.client.ServerProxy(common_url)
        self.models = xmlrpc.client.ServerProxy(object_url)
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})

    def notify_partner(
        self,
        partner_id: int | None,
        title: str,
        message: str,
        type: str = "info",
    ) -> bool:
        if not partner_id:
            return False

        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                "bus.bus",
                "send_rpc_notification",
                [partner_id, title, message, type],
            )
        except Exception as exc:
            print(f"[OdooNotifier] Error enviando notificación: {exc}")
            return False