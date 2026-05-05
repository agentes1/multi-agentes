import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ROUTE_HINTS = {
    "budget": {
        "primary": ("presupuesto", "cotizacion", "cotización", "precio", "propuesta", "budget"),
        "secondary": (
            "presupuesto", "precio", "propuesta", "cotizacion", "cotización",
            "implantar", "implantacion", "implantación", "automatizacion",
            "automatización", "formacion", "formación", "modulos", "módulos", "desarrollo",
        ),
    },
    "sales": {
        "primary": ("pipeline", "lead", "leads", "oportunidades", "ventas"),
        "secondary": ("pipeline", "lead", "leads", "oportunidades", "ventas", "comercial", "seguimiento comercial"),
    },
}

BUSINESS = {
    "budget": {
        "url_param": "helpdesk_virtual_assistant.backend_budget_from_ticket_url",
        "env": "HELP_DESK_VIRTUAL_ASSISTANT_BUDGET_FROM_TICKET_URL",
        "default": "http://assistant-backend:8000/assistant/budget-from-ticket",
        "thread": "odoo-ticket-budget-",
        "done_flag": "assistant_budget_created",
        "record_id": "assistant_sale_order_id",
        "response": "assistant_budget_response",
        "id_keys": ("sale_order_id", ("quote_summary", "sale_order_id")),
        "summary_key": "quote_summary",
        "summary_name": "sale_order_name",
        "ok_error": "Budget backend returned an error",
        "final": "He creado el presupuesto {ref}. Si quieres, puedes indicarme una nueva necesidad y la reviso por este chat.",
    },
    "sales": {
        "url_param": "helpdesk_virtual_assistant.backend_sales_from_ticket_url",
        "env": "HELP_DESK_VIRTUAL_ASSISTANT_SALES_FROM_TICKET_URL",
        "default": "http://assistant-backend:8000/assistant/sales-from-ticket",
        "thread": "odoo-ticket-sales-",
        "done_flag": "assistant_sales_created",
        "record_id": "assistant_crm_lead_id",
        "response": "assistant_sales_response",
        "id_keys": ("crm_lead_id", ("crm_summary", "id")),
        "summary_key": "crm_summary",
        "summary_name": "name",
        "ok_error": "Sales backend returned an error",
        "final": "He creado la oportunidad comercial {ref}. Si quieres, puedes indicarme una nueva necesidad y la reviso por este chat.",
    },
}


class HelpdeskTicket(models.Model):
    """Conecta tickets de Odoo con el asistente, Discuss y agentes de negocio."""

    _inherit = "helpdesk.ticket"

    assistant_channel_id = fields.Many2one("discuss.channel", string="Assistant Discuss Channel", copy=False, readonly=True)
    assistant_route_name = fields.Char(string="Assistant Route", copy=False, readonly=True)

    assistant_budget_created = fields.Boolean(string="Assistant Budget Created", copy=False, readonly=True)
    assistant_sale_order_id = fields.Integer(string="Assistant Sale Order ID", copy=False, readonly=True)
    assistant_budget_response = fields.Text(string="Assistant Budget Response", copy=False, readonly=True)

    assistant_sales_created = fields.Boolean(string="Assistant Sales Created", copy=False, readonly=True)
    assistant_crm_lead_id = fields.Integer(string="Assistant CRM Lead ID", copy=False, readonly=True)
    assistant_sales_response = fields.Text(string="Assistant Sales Response", copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Crea tickets y abre chat salvo si vienen de email o de un flujo interno."""
        tickets = super().create(vals_list)
        if self._skip_initial_chat():
            return tickets

        for ticket in tickets:
            try:
                ticket._open_virtual_assistant_chat()
            except Exception:
                _logger.exception("No se pudo abrir el chat del asistente para el ticket %s", ticket.id)
        return tickets

    def write(self, vals):
        """Al cerrar el ticket, crea presupuesto o lead según la ruta detectada."""
        to_process = self.env["helpdesk.ticket"]
        if vals.get("kanban_state") == "done" and not self.env.context.get("skip_assistant_budget_trigger"):
            to_process = self.filtered(lambda t: t.kanban_state != "done")

        result = super().write(vals)

        for ticket in to_process:
            try:
                ticket._run_business_flow(ticket._resolve_ready_state_route())
            except Exception:
                _logger.exception("No se pudo crear el registro de negocio para el ticket %s", ticket.id)
        return result

    def _skip_initial_chat(self):
        """Evita chat si el ticket viene de email o de un flujo interno."""
        return (
            self.env.context.get("assistant_ticket_origin") == "email"
            or self.env.context.get("skip_virtual_assistant_chat")
            or self.env.context.get("skip_virtual_assistant_flow")
        )

    def _resolve_ready_state_route(self):
        """Devuelve 'budget', 'sales' o vacío según ruta guardada o texto del ticket."""
        self.ensure_one()
        route = (self.assistant_route_name or "").strip().lower()
        if route in {"budget", "sales"}:
            return route
        if route == "general":
            return ""

        text = self._clean_text(" ".join(filter(None, [
            self.name,
            self.description,
            self.team_id.name if self.team_id else "",
            self.ticket_type_id.name if "ticket_type_id" in self._fields and self.ticket_type_id else "",
        ])))

        for name, hints in ROUTE_HINTS.items():
            if any(self._clean_text(term) in text for term in hints["primary"]):
                return name

        scores = {
            name: sum(self._clean_text(term) in text for term in hints["secondary"])
            for name, hints in ROUTE_HINTS.items()
        }
        if scores["budget"] >= 2 and scores["budget"] > scores["sales"]:
            return "budget"
        if scores["sales"] >= 2 and scores["sales"] >= scores["budget"]:
            return "sales"
        return ""

    @staticmethod
    def _clean_text(value):
        """Normaliza texto simple para comparar rutas."""
        return " ".join(re.sub(r"<[^>]+>", " ", str(value or "").lower()).split())

    def _run_business_flow(self, route):
        """Lanza el agente de negocio elegido y guarda su resultado en Odoo."""
        self.ensure_one()
        if route not in BUSINESS:
            return

        cfg = BUSINESS[route]
        if self[cfg["done_flag"]] or self[cfg["record_id"]]:
            return

        parsed = self._post_json(self._endpoint(cfg), self._ticket_payload(cfg["thread"]))
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("error") or cfg["ok_error"])

        record_id = self._nested_get(parsed, *cfg["id_keys"])
        self.with_context(skip_assistant_budget_trigger=True).sudo().write({
            cfg["done_flag"]: bool(record_id),
            cfg["record_id"]: record_id or 0,
            cfg["response"]: parsed.get("reply_text", ""),
        })
        self._post_assistant_completion_to_discuss(self._completion_message(route, parsed, record_id))

    def _ticket_payload(self, thread_prefix):
        """Crea el payload común que entiende el backend."""
        self.ensure_one()
        partner = self.partner_id
        return {
            "ticket_id": self.id,
            "notify_partner_id": self._notify_partner_id(),
            "title": self.name or "",
            "description": self.description or "",
            "partner_id": partner.id if partner else None,
            "partner_name": partner.name if partner else self.partner_name or "",
            "partner_email": partner.email if partner else self.partner_email or "",
            "thread_id": f"{thread_prefix}{self.id}",
        }

    def _endpoint(self, cfg):
        """Lee URL desde parámetros de Odoo, variable Docker o valor por defecto."""
        return self.env["ir.config_parameter"].sudo().get_param(
            cfg["url_param"],
            os.getenv(cfg["env"], cfg["default"]),
        )

    def _post_json(self, url, payload, timeout=180):
        """Envía JSON al backend y devuelve la respuesta parseada."""
        req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())

    @staticmethod
    def _nested_get(data, *keys):
        """Busca valores directos o anidados: 'id' o ('summary', 'id')."""
        for key in keys:
            if isinstance(key, tuple):
                value = data.get(key[0], {}).get(key[1])
            else:
                value = data.get(key)
            if value:
                return value
        return None

    def _open_virtual_assistant_chat(self):
        """Abre Discuss, publica recepción y después la respuesta real del backend."""
        self.ensure_one()
        assistant = self._virtual_assistant_user()
        recipient = self._recipient_partner()

        if not assistant or not recipient:
            _logger.warning("Faltan usuarios/partners para abrir chat en ticket %s", self.id)
            return

        channel = self._get_or_create_channel(assistant, recipient)
        self.sudo().write({"assistant_channel_id": channel.id})

        initial = self._initial_message()
        self._post_to_channel(channel, assistant, initial)

        result = self._fetch_virtual_assistant_message()
        route = str(result.get("route_name", "")).strip()
        message = str(result.get("reply_text", "")).strip()

        if route:
            self.sudo().write({"assistant_route_name": route})
        if message and message != initial:
            self._post_to_channel(channel, assistant, message)

    def _get_or_create_channel(self, assistant, recipient):
        """Reutiliza o crea un canal Discuss para evitar duplicados."""
        self.ensure_one()
        channel_name = f"Ticket {self.id} - Asistente Virtual"
        Channel = self.env["discuss.channel"].sudo()

        channel = self.assistant_channel_id.sudo().exists() or Channel.search([("name", "=", channel_name)], limit=1)
        if channel:
            return channel

        vals = {"name": channel_name, "channel_type": "chat"}
        partners = [(4, recipient.id), (4, assistant.partner_id.id)]

        if "partner_ids" in Channel._fields:
            vals["partner_ids"] = partners
        elif "channel_partner_ids" in Channel._fields:
            vals["channel_partner_ids"] = partners

        return Channel.create(vals)

    def _fetch_virtual_assistant_message(self):
        """Pide al backend la primera respuesta del semantic router/agente."""
        self.ensure_one()
        cfg = {
            "url_param": "helpdesk_virtual_assistant.backend_ticket_entry_url",
            "env": "HELP_DESK_VIRTUAL_ASSISTANT_TICKET_ENTRY_URL",
            "default": "http://assistant-backend:8000/assistant/ticket-entry",
        }

        try:
            parsed = self._post_json(self._endpoint(cfg), self._ticket_payload("odoo-ticket-"))
            if str(parsed.get("reply_text", "")).strip():
                return parsed
            _logger.warning("Backend sin reply_text para ticket %s", self.id)
        except (HTTPError, URLError) as error:
            _logger.exception("Backend no disponible para ticket %s: %s", self.id, error)
        except Exception:
            _logger.exception("Fallo inesperado llamando al backend para ticket %s", self.id)

        return {"reply_text": self._initial_message(), "route_name": ""}

    def _post_assistant_completion_to_discuss(self, message):
        """Publica el cierre del flujo de negocio en Discuss."""
        self.ensure_one()
        channel = self.assistant_channel_id.sudo().exists()
        assistant = self._virtual_assistant_user()
        if message and channel and assistant and assistant.partner_id:
            self._post_to_channel(channel, assistant, message)

    def _post_to_channel(self, channel, user, body):
        """Publica un mensaje como asistente evitando reentradas del flujo."""
        channel.with_context(skip_virtual_assistant_followup=True).with_user(user).message_post(
            body=body,
            author_id=user.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _completion_message(self, route, parsed, record_id):
        """Construye el mensaje final para budget o sales."""
        cfg = BUSINESS[route]
        summary = parsed.get(cfg["summary_key"], {}) or {}
        ref = summary.get(cfg["summary_name"]) or (f"ID {record_id}" if record_id else "sin referencia visible")
        return cfg["final"].format(ref=ref)

    def _virtual_assistant_user(self):
        """Devuelve el asignado o el usuario llamado Asistente Virtual."""
        self.ensure_one()
        if self.user_id and self.user_id.partner_id:
            return self.user_id
        return self.env["res.users"].sudo().search([("name", "=", "Asistente Virtual")], limit=1)

    def _recipient_partner(self):
        """Devuelve el partner destinatario del chat."""
        self.ensure_one()
        return self.partner_id or (self.create_uid.partner_id if self.create_uid else False)

    def _notify_partner_id(self):
        """Devuelve a quién notificar en Odoo."""
        self.ensure_one()
        return self.env.user.partner_id.id if self.env.user.partner_id else None

    def _initial_message(self):
        """Mensaje fijo de recepción del ticket."""
        self.ensure_one()
        return (
            f"Hola. Soy Asistente Virtual y he recibido tu ticket '{self.name}'. "
            "Estoy revisando tu solicitud para derivarla al agente adecuado."
        )
