import logging
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, models

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            try:
                ticket._open_virtual_assistant_chat()
            except Exception:
                _logger.exception(
                    "Virtual assistant chat could not be created for ticket %s",
                    ticket.id,
                )
        return tickets

    def _open_virtual_assistant_chat(self):
        self.ensure_one()

        assistant_user = self._get_virtual_assistant_user()
        if not assistant_user:
            _logger.warning(
                "No assistant user was found for ticket %s. Expected assigned user or 'Asistente Virtual'.",
                self.id,
            )
            return

        recipient_partner = self._get_ticket_recipient_partner()
        if not recipient_partner:
            _logger.warning(
                "No recipient partner was found for ticket %s. Chat will not be created.",
                self.id,
            )
            return

        partner_ids = [recipient_partner.id, assistant_user.partner_id.id]
        channel_name = f"Ticket {self.id} - Asistente Virtual"
        channel_model = self.env["discuss.channel"].sudo()

        channel = channel_model.search(
            [("name", "=", channel_name)],
            limit=1,
        )
        if not channel:
            create_vals = {
                "name": channel_name,
                "channel_type": "chat",
            }
            partner_commands = [(4, partner_id) for partner_id in partner_ids]
            if "partner_ids" in channel_model._fields:
                create_vals["partner_ids"] = partner_commands
            elif "channel_partner_ids" in channel_model._fields:
                create_vals["channel_partner_ids"] = partner_commands

            channel = channel_model.create(create_vals)

        initial_message = self._build_virtual_assistant_message()
        channel.with_user(assistant_user).message_post(
            body=initial_message,
            author_id=assistant_user.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        message = self._fetch_virtual_assistant_message()
        if message and message != initial_message:
            channel.with_user(assistant_user).message_post(
                body=message,
                author_id=assistant_user.partner_id.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    def _get_virtual_assistant_user(self):
        self.ensure_one()
        if self.user_id and self.user_id.partner_id:
            return self.user_id

        return self.env["res.users"].sudo().search(
            [("name", "=", "Asistente Virtual")],
            limit=1,
        )

    def _get_ticket_recipient_partner(self):
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        if self.create_uid and self.create_uid.partner_id:
            return self.create_uid.partner_id
        return False

    def _build_virtual_assistant_message(self):
        self.ensure_one()
        return (
            f"Hola. Soy Asistente Virtual y he recibido tu ticket '{self.name}'. "
            "Estoy revisando tu solicitud para derivarla al agente adecuado."
        )

    def _fetch_virtual_assistant_message(self):
        self.ensure_one()
        endpoint_url = self._get_backend_endpoint_url()
        payload = {
            "ticket_id": self.id,
            "title": self.name or "",
            "description": self.description or "",
            "partner_name": self.partner_id.name if self.partner_id else "",
            "partner_email": self.partner_id.email if self.partner_id else "",
            "thread_id": f"odoo-ticket-{self.id}",
        }

        request = Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                raw_body = response.read().decode("utf-8")
            parsed = json.loads(raw_body)
            reply_text = str(parsed.get("reply_text", "")).strip()
            if reply_text:
                return reply_text
            _logger.warning(
                "Assistant backend returned no reply_text for ticket %s. Falling back to default message.",
                self.id,
            )
        except HTTPError as error:
            _logger.exception(
                "Assistant backend returned HTTP error for ticket %s: %s",
                self.id,
                error,
            )
        except URLError as error:
            _logger.exception(
                "Assistant backend could not be reached for ticket %s: %s",
                self.id,
                error,
            )
        except Exception:
            _logger.exception(
                "Assistant backend call failed unexpectedly for ticket %s",
                self.id,
            )

        return self._build_virtual_assistant_message()

    def _get_backend_endpoint_url(self):
        self.ensure_one()
        parameter_model = self.env["ir.config_parameter"].sudo()
        return parameter_model.get_param(
            "helpdesk_virtual_assistant.backend_ticket_entry_url",
            os.getenv(
                "HELP_DESK_VIRTUAL_ASSISTANT_TICKET_ENTRY_URL",
                "http://assistant-backend:8000/assistant/ticket-entry",
            ),
        )
