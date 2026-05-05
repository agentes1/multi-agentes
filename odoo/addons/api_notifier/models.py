from odoo import models, api

class BusBus(models.Model):
    _inherit = 'bus.bus'
    @api.model
    def send_rpc_notification(self, partner_id, title, message, type='info'):
        """Public wrapper to send notifications via XML-RPC"""
        # The channel targets a specific partner (user)
        channel = (self.env.cr.dbname, 'res.partner', partner_id)
        notification = {
            "type": type,
            "title": title,
            "message": message,
            "sticky": False,
        }
        # Internally, Odoo allows calling private methods
        self.env['bus.bus']._sendone(channel, 'simple_notification', notification)
        return True
