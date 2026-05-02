import json
import logging
import os
import re
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailInboxMessage(models.Model):
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
    partner_id = fields.Many2one("res.partner", string="Related Partner", tracking=True)

    state = fields.Selection(
        [
            ("new", "New"),
            ("processing", "Processing"),
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
        """Guarda en Odoo el correo entrante recibido por fetchmail."""
        values = dict(custom_values or {})

        email_from = (
            msg_dict.get("email_from")
            or msg_dict.get("from")
            or msg_dict.get("author_email")
            or ""
        )

        partner_id = False
        author_id = msg_dict.get("author_id")
        if author_id:
            partner = self.env["res.partner"].browse(author_id).exists()
            partner_id = partner.id if partner else False

        values.update(
            {
                "subject": msg_dict.get("subject") or "(No subject)",
                "email_from": email_from,
                "email_to": msg_dict.get("to") or msg_dict.get("email_to") or msg_dict.get("recipients") or "",
                "email_cc": msg_dict.get("cc") or msg_dict.get("email_cc") or "",
                "body_html": msg_dict.get("body") or msg_dict.get("body_html") or msg_dict.get("text") or "",
                "message_id": msg_dict.get("message_id"),
                "received_date": fields.Datetime.now(),
                "partner_id": partner_id,
                "state": "new",
            }
        )

        return self.create(values)

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y deja su procesamiento para el cron."""
        records = super().create(vals_list)
        _logger.info("Queued %s incoming inbox message(s).", len(records))
        return records

    @api.model
    def _cron_process_pending_intake(self, limit=5):
        """Procesa correos pendientes de forma asíncrona."""
        records = self.search(
            [("state", "=", "new")],
            order="received_date asc, id asc",
            limit=limit,
        )

        for record in records:
            try:
                record.sudo().write({"state": "processing"})
                record._trigger_intake_processing()
            except Exception:
                _logger.exception("Could not process inbox record %s.", record.id)
                record.sudo().write(
                    {
                        "state": "error",
                        "agent_response": "Error interno al procesar el correo entrante.",
                    }
                )

        return True

    def _trigger_intake_processing(self):
        """Envía el correo normalizado al backend del agente de intake."""
        self.ensure_one()

        if self.state not in ("new", "processing"):
            return

        result = self._call_intake_backend(self._build_backend_payload())

        if result.get("ok"):
            self._mark_as_processed(result)
        else:
            self.sudo().write(
                {
                    "state": "error",
                    "agent_response": result.get("error") or "No se pudo procesar el correo entrante.",
                }
            )

    def _build_backend_payload(self):
        """Construye el payload que recibirá el agente de intake."""
        self.ensure_one()

        _, sender_email = parseaddr(self.email_from or "")

        # No mandamos self.partner_id como cliente.
        # Ese partner lo asigna Odoo al recibir el correo y puede ser la empresa interna.
        return {
            "channel": "email",
            "inbox_id": self.id,
            "subject": self.subject or "",
            "from": self.email_from or "",
            "email_from": self.email_from or "",
            "email_to": self.email_to or "",
            "email_cc": self.email_cc or "",
            "body_html": self.body_html or "",
            "body": self._extract_plain_body(),
            "message_id": self.message_id or "",
            "sender_name": "",
            "sender_email": sender_email or "",
            "received_date": str(self.received_date or ""),
            "thread_id": f"odoo-mail-inbox-{self.id}",
        }

    def _call_intake_backend(self, payload):
        """Llama al backend que ejecuta el agente de intake."""
        self.ensure_one()

        endpoint_url = self.env["ir.config_parameter"].sudo().get_param(
            "mail_inbox_input.backend_incoming_email_url",
            os.getenv(
                "MAIL_INBOX_INPUT_BACKEND_INCOMING_EMAIL_URL",
                "http://assistant-backend:8000/assistant/incoming-email",
            ),
        )

        request = Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))

        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            _logger.exception(
                "Backend returned HTTP error for inbox record %s: %s. Body: %s",
                self.id,
                error,
                error_body,
            )

        except URLError as error:
            _logger.exception("Backend could not be reached for inbox record %s: %s", self.id, error)

        except Exception:
            _logger.exception("Backend call failed for inbox record %s.", self.id)

        return {"ok": False, "error": "No se pudo contactar con el backend de intake."}

    def _mark_as_processed(self, result):
        """Marca el correo como procesado y envía respuesta si el backend la genera."""
        self.ensure_one()

        reply_text = result.get("reply_text") or result.get("final_text") or ""

        self.sudo().write(
            {
                "state": "processed",
                "agent_response": reply_text,
                "generated_ticket_id": result.get("ticket_id") or 0,
            }
        )

        if reply_text:
            self._send_reply_email(reply_text)

    def _extract_plain_body(self):
        """Convierte el HTML del correo en texto plano básico."""
        self.ensure_one()

        plain_body = re.sub(r"<[^>]+>", " ", self.body_html or "")
        return re.sub(r"\s+", " ", plain_body).strip()

    def _send_reply_email(self, reply_text):
        """Envía una respuesta por email al remitente original."""
        self.ensure_one()

        _, recipient_email = parseaddr(self.email_from or "")
        recipient_email = (recipient_email or self.email_from or "").strip()

        if not recipient_email:
            _logger.warning("No recipient email found for inbox record %s.", self.id)
            return False

        subject = self.subject or "(Sin asunto)"
        body_html = f"<div>{reply_text.replace(chr(10), '<br/>')}</div>"

        self.env["mail.mail"].sudo().create(
            {
                "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
                "body_html": body_html,
                "email_to": recipient_email,
            }
        ).send()

        return True

    def action_mark_processed(self):
        """Marca manualmente el correo como procesado."""
        for record in self:
            record.state = "processed"
        return True

    def action_mark_error(self):
        """Marca manualmente el correo como error."""
        for record in self:
            record.state = "error"
        return True

    def action_reset_to_new(self):
        """Devuelve el correo a estado pendiente."""
        for record in self:
            record.state = "new"
        return True

    def action_process_now(self):
        """Lanza manualmente el procesamiento de correos pendientes o con error."""
        for record in self:
            if record.state in ("new", "error"):
                record.sudo().write({"state": "processing"})
                record._trigger_intake_processing()
        return True