import json
import logging
import os
import re
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

BACKEND_PARAM = "mail_inbox_input.backend_incoming_email_url"
BACKEND_ENV = "MAIL_INBOX_INPUT_BACKEND_INCOMING_EMAIL_URL"
BACKEND_URL = "http://assistant-backend:8000/assistant/incoming-email"


class MailInboxMessage(models.Model):
    """Entrada de correos: normaliza email, llama al agente intake y responde."""

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
        [("new", "New"), ("processing", "Processing"), ("processed", "Processed"), ("error", "Error")],
        string="State",
        default="new",
        tracking=True,
    )

    agent_response = fields.Text(string="Agent Response", readonly=True)
    generated_ticket_id = fields.Integer(string="Generated Ticket ID", readonly=True)

    @api.model
    def message_new(self, msg, custom_values=None):
        """Crea un registro desde un correo entrante de Odoo/fetchmail."""
        message_id = msg.get("message_id")
        if message_id and self.search([("message_id", "=", message_id)], limit=1):
            _logger.info("Correo duplicado ignorado: %s", message_id)
            return self.search([("message_id", "=", message_id)], limit=1)

        vals = dict(custom_values or {})
        vals.update({
            "subject": msg.get("subject") or "(No subject)",
            "email_from": self._first(msg, "email_from", "from", "author_email"),
            "email_to": self._first(msg, "to", "email_to", "recipients"),
            "email_cc": self._first(msg, "cc", "email_cc"),
            "body_html": self._first(msg, "body", "body_html", "text"),
            "message_id": message_id,
            "received_date": fields.Datetime.now(),
            "partner_id": self._author_partner_id(msg),
            "state": "new",
        })
        return self.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Encola correos; el cron se encarga del procesamiento real."""
        records = super().create(vals_list)
        _logger.info("Correos encolados: %s", len(records))
        return records

    @api.model
    def _cron_process_pending_intake(self, limit=5):
        """Procesa los correos pendientes en orden de llegada."""
        for record in self.search([("state", "=", "new")], order="received_date asc, id asc", limit=limit):
            record._safe_process()
        return True
    
    def action_fetch_emails(self, *args, **kwargs):
        """Ejecuta fetchmail, procesa pendientes y reabre la lista con aviso."""
        servers = self.env["fetchmail.server"].sudo().search([("active", "=", True)])

        if not servers:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Sin servidores",
                    "message": "No hay servidores de correo entrante activos.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        for server in servers:
            server.fetch_mail()

        #self.env["mail.inbox.message"].sudo()._cron_process_pending_intake(limit=20)

        action = self.env.ref("mail_inbox_input.action_mail_inbox_message").sudo().read()[0]

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Correos actualizados",
                "message": "Odoo ha buscado correos nuevos y procesado los pendientes.",
                "type": "success",
                "sticky": False,
                "next": action,
            },
        }

    def _safe_process(self):
        """Procesa un correo y guarda error controlado si algo falla."""
        self.ensure_one()
        try:
            self.sudo().write({"state": "processing"})
            self._trigger_intake_processing()
        except Exception:
            _logger.exception("No se pudo procesar el correo %s", self.id)
            self._set_error("Error interno al procesar el correo entrante.")

    def _trigger_intake_processing(self):
        """Evita duplicados, llama al backend y guarda el resultado."""
        self.ensure_one()
        if self.state not in ("new", "processing"):
            return

        duplicate = self._processed_duplicate()
        if duplicate:
            self._reuse_duplicate(duplicate)
            return

        result = self._post_json(self._backend_url(), self._payload())
        self._mark_as_processed(result) if result.get("ok") else self._set_error(
            result.get("error") or "No se pudo procesar el correo entrante."
        )

    def _payload(self):
        """Construye el contexto mínimo para el agente intake."""
        self.ensure_one()
        _, sender_email = parseaddr(self.email_from or "")
        return {
            "channel": "email",
            "inbox_id": self.id,
            "notify_partner_id": self._notify_partner_id(),
            "subject": self.subject or "",
            "from": self.email_from or "",
            "email_from": self.email_from or "",
            "email_to": self.email_to or "",
            "email_cc": self.email_cc or "",
            "body_html": self.body_html or "",
            "body": self._plain_body(),
            "message_id": self.message_id or "",
            "sender_name": "",
            "sender_email": sender_email or "",
            "received_date": str(self.received_date or ""),
            "thread_id": f"odoo-mail-inbox-{self.id}",
        }

    def _post_json(self, url, payload):
        """Envía el email normalizado al backend del agente."""
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode())
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            _logger.exception("HTTP error en inbox %s: %s. Body: %s", self.id, error, body)
        except URLError as error:
            _logger.exception("Backend no disponible para inbox %s: %s", self.id, error)
        except Exception:
            _logger.exception("Fallo llamando al backend para inbox %s", self.id)

        return {"ok": False, "error": "No se pudo contactar con el backend de intake."}

    def _mark_as_processed(self, result):
        """Guarda respuesta, ticket generado y contesta por email si procede."""
        self.ensure_one()
        reply = result.get("reply_text") or result.get("final_text") or ""

        self.sudo().write({
            "state": "processed",
            "agent_response": reply,
            "generated_ticket_id": result.get("ticket_id") or 0,
        })

        if reply:
            self._send_reply_email(reply)

    def _send_reply_email(self, reply):
        """Responde al remitente original usando mail.mail."""
        self.ensure_one()
        _, email = parseaddr(self.email_from or "")
        email = (email or self.email_from or "").strip()

        if not email:
            _logger.warning("Sin destinatario para inbox %s", self.id)
            return False

        subject = self.subject or "(Sin asunto)"
        self.env["mail.mail"].sudo().create({
            "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
            "body_html": f"<div>{reply.replace(chr(10), '<br/>')}</div>",
            "email_to": email,
        }).send()
        return True

    def _processed_duplicate(self):
        """Busca otro correo igual que ya haya generado ticket."""
        self.ensure_one()
        return self.message_id and self.search([
            ("id", "!=", self.id),
            ("message_id", "=", self.message_id),
            ("generated_ticket_id", "!=", 0),
        ], limit=1)

    def _reuse_duplicate(self, duplicate):
        """Reutiliza resultado de un correo duplicado ya procesado."""
        self.ensure_one()
        self.sudo().write({
            "state": "processed",
            "agent_response": duplicate.agent_response,
            "generated_ticket_id": duplicate.generated_ticket_id,
        })
        _logger.info("Inbox %s reutiliza ticket %s de inbox %s", self.id, duplicate.generated_ticket_id, duplicate.id)

    def _set_error(self, message):
        """Marca el registro como error con mensaje legible."""
        self.sudo().write({"state": "error", "agent_response": message})

    def _plain_body(self):
        """Convierte HTML en texto plano básico."""
        self.ensure_one()
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", self.body_html or "")).strip()

    def _backend_url(self):
        """Obtiene URL desde Odoo, Docker o valor por defecto."""
        return self.env["ir.config_parameter"].sudo().get_param(
            BACKEND_PARAM,
            os.getenv(BACKEND_ENV, BACKEND_URL),
        )

    def _notify_partner_id(self):
        """Lee partner a notificar; si falla, usa el usuario actual."""
        value = self.env["ir.config_parameter"].sudo().get_param("mail_inbox_input.notify_partner_id")
        try:
            return int(value) if value else self.env.user.partner_id.id
        except (TypeError, ValueError):
            return self.env.user.partner_id.id

    def _author_partner_id(self, msg):
        """Convierte author_id del email en partner_id válido."""
        partner = self.env["res.partner"].browse(msg.get("author_id")).exists() if msg.get("author_id") else False
        return partner.id if partner else False

    @staticmethod
    def _first(data, *keys):
        """Devuelve el primer valor no vacío de un dict."""
        return next((data.get(key) for key in keys if data.get(key)), "")

    def action_mark_processed(self):
        """Marca manualmente como procesado."""
        self.write({"state": "processed"})
        return True

    def action_mark_error(self):
        """Marca manualmente como error."""
        self.write({"state": "error"})
        return True

    def action_reset_to_new(self):
        """Devuelve el correo a pendiente."""
        self.write({"state": "new"})
        return True

    def action_process_now(self):
        """Procesa manualmente correos pendientes o con error."""
        for record in self.filtered(lambda r: r.state in ("new", "error")):
            record.sudo().write({"state": "processing"})
            record._trigger_intake_processing()
        return True