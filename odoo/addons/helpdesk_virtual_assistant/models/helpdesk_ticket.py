import logging
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_BUDGET_HINTS = (
    "presupuesto",
    "precio",
    "propuesta",
    "cotizacion",
    "cotización",
    "implantar",
    "implantacion",
    "implantación",
    "automatizacion",
    "automatización",
    "formacion",
    "formación",
    "modulos",
    "módulos",
    "soporte mensual",
    "desarrollo",
)
_SALES_HINTS = (
    "pipeline",
    "lead",
    "leads",
    "oportunidades",
    "ventas",
    "comercial",
    "seguimiento comercial",
)
_BUDGET_PRIMARY_HINTS = ("presupuesto", "cotizacion", "cotización", "precio", "propuesta")
_SALES_PRIMARY_HINTS = ("pipeline", "lead", "leads", "oportunidades", "ventas")


class HelpdeskTicket(models.Model):
    # Extensión de helpdesk.ticket que conecta el alta de tickets con el backend Python.
    # Este archivo solo se ocupa del arranque del flujo: abrir chat y pedir primera respuesta.
    _inherit = "helpdesk.ticket"

    assistant_channel_id = fields.Many2one(
        comodel_name="discuss.channel",
        string="Assistant Discuss Channel",
        copy=False,
        readonly=True,
    )
    assistant_route_name = fields.Char(
        string="Assistant Route",
        readonly=True,
        copy=False,
    )
    assistant_budget_created = fields.Boolean(
        string="Assistant Budget Created",
        readonly=True,
        copy=False,
    )
    assistant_sale_order_id = fields.Integer(
        string="Assistant Sale Order ID",
        readonly=True,
        copy=False,
    )
    assistant_budget_response = fields.Text(
        string="Assistant Budget Response",
        readonly=True,
        copy=False,
    )
    assistant_sales_created = fields.Boolean(
        string="Assistant Sales Created",
        readonly=True,
        copy=False,
    )
    assistant_crm_lead_id = fields.Integer(
        string="Assistant CRM Lead ID",
        readonly=True,
        copy=False,
    )
    assistant_sales_response = fields.Text(
        string="Assistant Sales Response",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        ticket_origin = self.env.context.get("assistant_ticket_origin")
        skip_assistant_chat = (
            ticket_origin == "email"
            or self.env.context.get("skip_virtual_assistant_chat")
            or self.env.context.get("skip_virtual_assistant_flow")
        )
        for ticket in tickets:
            # Los tickets creados desde email siguen convergiendo en helpdesk,
            # pero la primera respuesta debe salir por correo, no por Discuss.
            if skip_assistant_chat:
                _logger.info(
                    "Skipping virtual assistant Discuss chat for ticket %s because context origin is %s.",
                    ticket.id,
                    ticket_origin,
                )
                continue
            try:
                # Cada ticket nuevo arranca automáticamente una conversación en Discuss.
                ticket._open_virtual_assistant_chat()
            except Exception:
                _logger.exception(
                    "Virtual assistant chat could not be created for ticket %s",
                    ticket.id,
                )
        return tickets

    def write(self, vals):
        trigger_ready_tickets = self.env["helpdesk.ticket"]
        if vals.get("kanban_state") == "done" and not self.env.context.get("skip_assistant_budget_trigger"):
            trigger_ready_tickets = self.filtered(
                lambda ticket: (
                    ticket.kanban_state != "done"
                )
            )

        result = super().write(vals)

        for ticket in trigger_ready_tickets:
            try:
                route_name = ticket._resolve_ready_state_route()
                if route_name == "budget":
                    if not ticket.assistant_budget_created and not ticket.assistant_sale_order_id:
                        ticket._trigger_budget_from_ready_state()
                elif route_name == "sales":
                    if not ticket.assistant_sales_created and not ticket.assistant_crm_lead_id:
                        ticket._trigger_sales_from_ready_state()
            except Exception:
                _logger.exception(
                    "Assistant follow-up could not create a business record for ticket %s",
                    ticket.id,
                )

        return result

    def _resolve_ready_state_route(self):
        self.ensure_one()
        route_name = (self.assistant_route_name or "").strip().lower()
        if route_name in {"budget", "sales"}:
            return route_name

        text = self._normalize_route_text(" ".join(filter(None, [self.name or "", self.description or ""])))
        if any(self._normalize_route_text(term) in text for term in _BUDGET_PRIMARY_HINTS):
            return "budget"
        budget_hits = self._count_route_hints(text, _BUDGET_HINTS)
        sales_hits = self._count_route_hints(text, _SALES_HINTS)
        if budget_hits >= 2 and budget_hits > sales_hits:
            return "budget"
        if any(self._normalize_route_text(term) in text for term in _SALES_PRIMARY_HINTS):
            return "sales"
        if sales_hits >= 2 and sales_hits >= budget_hits:
            return "sales"
        return ""

    @staticmethod
    def _normalize_route_text(value):
        text = re.sub(r"<[^>]+>", " ", str(value or "").lower())
        return " ".join(text.split())

    @classmethod
    def _count_route_hints(cls, text, hints):
        return sum(1 for term in hints if cls._normalize_route_text(term) in text)

    def _trigger_budget_from_ready_state(self):
        self.ensure_one()
        if self.assistant_budget_created or self.assistant_sale_order_id:
            return

        endpoint_url = self._get_budget_from_ticket_endpoint_url()
        payload = {
            "ticket_id": self.id,
            "title": self.name or "",
            "description": self.description or "",
            "partner_id": self.partner_id.id if self.partner_id else None,
            "partner_name": self.partner_id.name if self.partner_id else self.partner_name or "",
            "partner_email": self.partner_id.email if self.partner_id else self.partner_email or "",
            "thread_id": f"odoo-ticket-budget-{self.id}",
        }

        request = Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=180) as response:
            raw_body = response.read().decode("utf-8")
        parsed = json.loads(raw_body)

        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("error") or "Budget backend returned an error")

        sale_order_id = parsed.get("sale_order_id") or parsed.get("quote_summary", {}).get("sale_order_id")
        self.with_context(skip_assistant_budget_trigger=True).sudo().write(
            {
                "assistant_budget_created": bool(sale_order_id),
                "assistant_sale_order_id": sale_order_id or 0,
                "assistant_budget_response": parsed.get("reply_text", ""),
            }
        )
        self._post_assistant_completion_to_discuss(self._build_budget_completion_message(parsed))

    def _get_budget_from_ticket_endpoint_url(self):
        self.ensure_one()
        return self.env["ir.config_parameter"].sudo().get_param(
            "helpdesk_virtual_assistant.backend_budget_from_ticket_url",
            os.getenv(
                "HELP_DESK_VIRTUAL_ASSISTANT_BUDGET_FROM_TICKET_URL",
                "http://assistant-backend:8000/assistant/budget-from-ticket",
            ),
        )

    def _trigger_sales_from_ready_state(self):
        self.ensure_one()
        if self.assistant_sales_created or self.assistant_crm_lead_id:
            return

        endpoint_url = self._get_sales_from_ticket_endpoint_url()
        payload = {
            "ticket_id": self.id,
            "title": self.name or "",
            "description": self.description or "",
            "partner_id": self.partner_id.id if self.partner_id else None,
            "partner_name": self.partner_id.name if self.partner_id else self.partner_name or "",
            "partner_email": self.partner_id.email if self.partner_id else self.partner_email or "",
            "thread_id": f"odoo-ticket-sales-{self.id}",
        }

        request = Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=180) as response:
            raw_body = response.read().decode("utf-8")
        parsed = json.loads(raw_body)

        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("error") or "Sales backend returned an error")

        crm_lead_id = parsed.get("crm_lead_id") or parsed.get("crm_summary", {}).get("id")
        self.with_context(skip_assistant_budget_trigger=True).sudo().write(
            {
                "assistant_sales_created": bool(crm_lead_id),
                "assistant_crm_lead_id": crm_lead_id or 0,
                "assistant_sales_response": parsed.get("reply_text", ""),
            }
        )
        self._post_assistant_completion_to_discuss(self._build_sales_completion_message(parsed))

    def _get_sales_from_ticket_endpoint_url(self):
        self.ensure_one()
        return self.env["ir.config_parameter"].sudo().get_param(
            "helpdesk_virtual_assistant.backend_sales_from_ticket_url",
            os.getenv(
                "HELP_DESK_VIRTUAL_ASSISTANT_SALES_FROM_TICKET_URL",
                "http://assistant-backend:8000/assistant/sales-from-ticket",
            ),
        )

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

        # La apertura del chat debe ser idempotente para evitar duplicados si Odoo
        # dispara el flujo de creacion del ticket mas de una vez.
        channel = self.assistant_channel_id.sudo().exists()
        if not channel:
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

        if self.assistant_channel_id != channel:
            self.sudo().write({"assistant_channel_id": channel.id})

        # Primer mensaje fijo: confirma recepción antes de consultar al semantic router.
        initial_message = self._build_virtual_assistant_message()
        channel.with_context(skip_virtual_assistant_followup=True).with_user(assistant_user).message_post(
            body=initial_message,
            author_id=assistant_user.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Segundo mensaje: respuesta real del backend según ruta/agente seleccionado.
        assistant_result = self._fetch_virtual_assistant_message()
        route_name = str(assistant_result.get("route_name", "")).strip()
        message = str(assistant_result.get("reply_text", "")).strip()

        fields_to_update = {}
        if route_name:
            fields_to_update["assistant_route_name"] = route_name
        if fields_to_update:
            self.sudo().write(fields_to_update)

        if message and message != initial_message:
            channel.with_context(skip_virtual_assistant_followup=True).with_user(assistant_user).message_post(
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

    def _post_assistant_completion_to_discuss(self, message):
        self.ensure_one()
        if not message:
            return

        channel = self.assistant_channel_id.sudo().exists()
        assistant_user = self._get_virtual_assistant_user()
        if not channel or not assistant_user or not assistant_user.partner_id:
            return

        channel.with_context(skip_virtual_assistant_followup=True).with_user(assistant_user).message_post(
            body=message,
            author_id=assistant_user.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _build_budget_completion_message(self, parsed):
        self.ensure_one()
        quote_summary = parsed.get("quote_summary", {}) or {}
        sale_order_name = quote_summary.get("sale_order_name")
        sale_order_id = parsed.get("sale_order_id") or quote_summary.get("sale_order_id")

        reference = sale_order_name or (f"ID {sale_order_id}" if sale_order_id else "sin referencia visible")
        return (
            f"He creado el presupuesto {reference}. "
            "Si quieres, puedes indicarme una nueva necesidad y la reviso por este chat."
        )

    def _build_sales_completion_message(self, parsed):
        self.ensure_one()
        crm_summary = parsed.get("crm_summary", {}) or {}
        opportunity_name = crm_summary.get("name")
        crm_lead_id = parsed.get("crm_lead_id") or crm_summary.get("id")

        reference = opportunity_name or (f"ID {crm_lead_id}" if crm_lead_id else "sin referencia visible")
        return (
            f"He creado la oportunidad comercial {reference}. "
            "Si quieres, puedes indicarme una nueva necesidad y la reviso por este chat."
        )

    def _fetch_virtual_assistant_message(self):
        self.ensure_one()
        endpoint_url = self._get_backend_endpoint_url()
        # El backend recibe el contexto mínimo del ticket y devuelve el texto ya preparado.
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
            with urlopen(request, timeout=180) as response:
                raw_body = response.read().decode("utf-8")
            parsed = json.loads(raw_body)
            reply_text = str(parsed.get("reply_text", "")).strip()
            if reply_text:
                return parsed
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

        return {"reply_text": self._build_virtual_assistant_message(), "route_name": ""}

    def _get_backend_endpoint_url(self):
        self.ensure_one()
        parameter_model = self.env["ir.config_parameter"].sudo()
        # Permite sobreescribir la URL desde parámetros de Odoo o variables de entorno Docker.
        return parameter_model.get_param(
            "helpdesk_virtual_assistant.backend_ticket_entry_url",
            os.getenv(
                "HELP_DESK_VIRTUAL_ASSISTANT_TICKET_ENTRY_URL",
                "http://assistant-backend:8000/assistant/ticket-entry",
            ),
        )
