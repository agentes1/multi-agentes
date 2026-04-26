import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailInboxMessage(models.Model):
    _name = "mail.inbox.message"
    _description = "Incoming Mail Message"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "received_date desc, id desc"
    _rec_name = "subject"

    subject = fields.Char(
        string="Subject",
        required=True,
        default="(No subject)",
        tracking=True,
    )

    email_from = fields.Char(
        string="From",
        tracking=True,
    )

    email_to = fields.Char(
        string="To",
        tracking=True,
    )

    email_cc = fields.Char(
        string="CC",
    )

    body_html = fields.Html(
        string="Email Body",
        sanitize=False,
    )

    message_id = fields.Char(
        string="Message-ID",
        index=True,
        copy=False,
    )

    received_date = fields.Datetime(
        string="Received Date",
        default=fields.Datetime.now,
        tracking=True,
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Related Partner",
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("processed", "Processed"),
            ("error", "Error"),
        ],
        string="State",
        default="new",
        tracking=True,
    )

    agent_response = fields.Text(
        string="Agent Response",
        readonly=True,
    )

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        Este método se ejecuta cuando fetchmail crea un registro nuevo
        desde un correo entrante.
        """

        _logger.info("MAIL_INBOX_INPUT msg_dict recibido: %s", msg_dict)

        values = dict(custom_values or {})

        email_from = (
            msg_dict.get("email_from")
            or msg_dict.get("from")
            or msg_dict.get("author_email")
        )

        email_to = (
            msg_dict.get("to")
            or msg_dict.get("email_to")
            or msg_dict.get("recipients")
        )

        email_cc = (
            msg_dict.get("cc")
            or msg_dict.get("email_cc")
        )

        body = (
            msg_dict.get("body")
            or msg_dict.get("body_html")
            or msg_dict.get("text")
            or ""
        )

        author_id = msg_dict.get("author_id")
        partner_id = False
        if author_id:
            partner = self.env["res.partner"].browse(author_id).exists()
            if partner:
                partner_id = partner.id

        values.update({
            "subject": msg_dict.get("subject") or "(No subject)",
            "email_from": email_from,
            "email_to": email_to,
            "email_cc": email_cc,
            "body_html": body,
            "message_id": msg_dict.get("message_id"),
            "received_date": fields.Datetime.now(),
            "partner_id": partner_id,
            "state": "new",
        })

        record = self.create(values)

        return record.id

    def action_mark_processed(self):
        for record in self:
            record.state = "processed"
        return True

    def action_mark_error(self):
        for record in self:
            record.state = "error"
        return True

    def action_reset_to_new(self):
        for record in self:
            record.state = "new"
        return True