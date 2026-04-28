import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailInboxMessage(models.Model):
    # Modelo de bandeja de entrada para correos que llegan a Odoo por fetchmail/Gmail.
    # Su función es registrar el correo y delegar el procesamiento real al intake agent.
    _name = "mail.inbox.message"
    _description = "Incoming Mail Message"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "received_date desc, id desc"
    _rec_name = "subject"

    subject = fields.Char(string="Subject", required=True, default="(No subject)", tracking=True)
    email_from = fields.Char(string="From", tracking=True)
    email_to = fields.Char(string="To", tracking=True)
    email_cc = fields.Char(string="CC")
    body_html = fields.Html(string="Email Body", sanitize=False)
    message_id = fields.Char(string="Message-ID", index=True, copy=False)
    received_date = fields.Datetime(string="Received Date", default=fields.Datetime.now, tracking=True)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Related Partner", tracking=True)
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
    agent_response = fields.Text(string="Agent Response", readonly=True)
    generated_ticket_id = fields.Integer(string="Generated Ticket ID", readonly=True)

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        # Hook que usa fetchmail al crear el registro desde un correo real entrante.
        _logger.info("MAIL_INBOX_INPUT msg_dict recibido: %s", msg_dict)

        values = dict(custom_values or {})
        email_from = msg_dict.get("email_from") or msg_dict.get("from") or msg_dict.get("author_email")
        email_to = msg_dict.get("to") or msg_dict.get("email_to") or msg_dict.get("recipients")
        email_cc = msg_dict.get("cc") or msg_dict.get("email_cc")
        body = msg_dict.get("body") or msg_dict.get("body_html") or msg_dict.get("text") or ""

        author_id = msg_dict.get("author_id")
        partner_id = False
        if author_id:
            partner = self.env["res.partner"].browse(author_id).exists()
            if partner:
                partner_id = partner.id

        values.update(
            {
                "subject": msg_dict.get("subject") or "(No subject)",
                "email_from": email_from,
                "email_to": email_to,
                "email_cc": email_cc,
                "body_html": body,
                "message_id": msg_dict.get("message_id"),
                "received_date": fields.Datetime.now(),
                "partner_id": partner_id,
                "state": "new",
            }
        )

        record = self.create(values)
        return record.id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            try:
                # Nada más guardar el correo, se intenta lanzar el flujo de intake.
                record._trigger_intake_processing()
            except Exception:
                _logger.exception(
                    "Incoming mail could not be processed by intake for inbox record %s",
                    record.id,
                )
                record.sudo().write(
                    {
                        "state": "error",
                        "agent_response": "Error interno al intentar procesar el correo entrante.",
                    }
                )
        return records

    def _trigger_intake_processing(self):
        self.ensure_one()
        if self.state != "new":
            return

        # El backend recibe el correo normalizado y se encarga de crear el ticket en Odoo.
        payload = {
            "inbox_id": self.id,
            "subject": self.subject or "",
            "email_from": self.email_from or "",
            "email_to": self.email_to or "",
            "email_cc": self.email_cc or "",
            "body_html": self.body_html or "",
            "body": self._extract_plain_body(),
            "message_id": self.message_id or "",
            "sender_name": self.partner_id.name if self.partner_id else "",
            "received_date": str(self.received_date or ""),
            "thread_id": f"odoo-mail-inbox-{self.id}",
        }
        result = self._call_intake_backend(payload)

        # Si intake crea el ticket correctamente, el propio create() del ticket seguirá el resto del flujo.
        if result.get("ok"):
            self.sudo().write(
                {
                    "state": "processed",
                    "agent_response": result.get("final_text", ""),
                    "generated_ticket_id": result.get("ticket_id") or 0,
                }
            )
            return

        self.sudo().write(
            {
                "state": "error",
                "agent_response": result.get("error") or "No se pudo procesar el correo entrante.",
            }
        )

    def _call_intake_backend(self, payload):
        self.ensure_one()
        endpoint_url = self.env["ir.config_parameter"].sudo().get_param(
            "mail_inbox_input.backend_incoming_email_url",
            os.getenv(
                "MAIL_INBOX_INPUT_BACKEND_INCOMING_EMAIL_URL",
                "http://assistant-backend:8000/assistant/incoming-email",
            ),
        )
        # Esta llamada no responde al cliente por email todavía; solo arranca la creación del ticket.
        request = Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=15) as response:
                raw_body = response.read().decode("utf-8")
            return json.loads(raw_body)
        except HTTPError as error:
            _logger.exception(
                "Incoming email backend returned HTTP error for inbox record %s: %s",
                self.id,
                error,
            )
        except URLError as error:
            _logger.exception(
                "Incoming email backend could not be reached for inbox record %s: %s",
                self.id,
                error,
            )
        except Exception:
            _logger.exception(
                "Incoming email backend call failed unexpectedly for inbox record %s",
                self.id,
            )

        return {
            "ok": False,
            "error": "No se pudo contactar con el backend de intake.",
        }

    def _extract_plain_body(self):
        self.ensure_one()
        body = self.body_html or ""
        plain_body = re.sub(r"<[^>]+>", " ", body)
        plain_body = re.sub(r"\s+", " ", plain_body).strip()
        return plain_body

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
