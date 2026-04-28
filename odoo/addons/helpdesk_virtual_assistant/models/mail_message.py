import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import api, models

_logger = logging.getLogger(__name__)

_CHANNEL_NAME_PATTERN = re.compile(r"^Ticket (?P<ticket_id>\d+) - Asistente Virtual$")


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for message in messages:
            try:
                message._trigger_virtual_assistant_followup()
            except Exception:
                _logger.exception(
                    "Virtual assistant follow-up could not be processed for message %s",
                    message.id,
                )
        return messages

    def _trigger_virtual_assistant_followup(self):
        self.ensure_one()
        channel = self._get_virtual_assistant_channel()
        if not channel:
            _logger.info(
                "Skipping discuss follow-up for message %s. model=%s res_id=%s author_id=%s body=%s",
                self.id,
                self.model,
                self.res_id,
                self.author_id.id if self.author_id else None,
                (self.body or "")[:120],
            )
            return

        assistant_user = self.env["res.users"].sudo().search(
            [("name", "=", "Asistente Virtual")],
            limit=1,
        )
        if not assistant_user or not assistant_user.partner_id:
            _logger.warning("Assistant user or partner not found while processing message %s", self.id)
            return

        if self.author_id and self.author_id.id == assistant_user.partner_id.id:
            _logger.info("Skipping assistant-authored discuss message %s to avoid loops", self.id)
            return

        body_text = self._extract_plain_body()
        if not body_text:
            _logger.info("Skipping discuss message %s because body is empty after normalization", self.id)
            return

        ticket_id = self._extract_ticket_id_from_channel_name(channel.name)
        ticket = self.env["helpdesk.ticket"].sudo().browse(ticket_id) if ticket_id else False
        payload = {
            "ticket_id": ticket.id if ticket else None,
            "ticket_title": ticket.name if ticket else "",
            "channel_id": channel.id,
            "channel_name": channel.name or "",
            "message_id": self.id,
            "author_name": self.author_id.name if self.author_id else "",
            "author_email": self.author_id.email if self.author_id else "",
            "body": body_text,
            "thread_id": f"odoo-discuss-{channel.id}",
        }

        reply_text = self._fetch_virtual_assistant_followup(payload)
        if not reply_text:
            _logger.info("Assistant backend returned no follow-up text for discuss message %s", self.id)
            return

        _logger.info(
            "Posting assistant follow-up to channel %s for discuss message %s using route backend",
            channel.id,
            self.id,
        )
        channel.with_user(assistant_user).message_post(
            body=reply_text,
            author_id=assistant_user.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _get_virtual_assistant_channel(self):
        self.ensure_one()
        model_name = self.model or ""
        if not self.res_id:
            return False

        candidate_models = []
        if model_name in {"discuss.channel", "mail.channel"}:
            candidate_models.append("discuss.channel")
        elif not model_name:
            candidate_models.extend(("discuss.channel", "mail.channel"))
        else:
            return False

        for candidate_model in candidate_models:
            channel = self.env[candidate_model].sudo().browse(self.res_id)
            if channel.exists() and channel.name and _CHANNEL_NAME_PATTERN.match(channel.name):
                return channel
        return False

    def _extract_plain_body(self):
        self.ensure_one()
        body = self.body or ""
        plain_body = re.sub(r"<[^>]+>", " ", body)
        plain_body = re.sub(r"\s+", " ", plain_body).strip()
        return plain_body

    @staticmethod
    def _extract_ticket_id_from_channel_name(channel_name):
        match = _CHANNEL_NAME_PATTERN.match(channel_name or "")
        if not match:
            return None
        return int(match.group("ticket_id"))

    def _fetch_virtual_assistant_followup(self, payload):
        self.ensure_one()
        endpoint_url = self.env["ir.config_parameter"].sudo().get_param(
            "helpdesk_virtual_assistant.backend_discuss_message_url",
            os.getenv(
                "HELP_DESK_VIRTUAL_ASSISTANT_DISCUSS_MESSAGE_URL",
                "http://assistant-backend:8000/assistant/discuss-message",
            ),
        )
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
                "Assistant backend returned no reply_text for discuss message %s.",
                self.id,
            )
        except HTTPError as error:
            _logger.exception(
                "Assistant backend returned HTTP error for discuss message %s: %s",
                self.id,
                error,
            )
        except URLError as error:
            _logger.exception(
                "Assistant backend could not be reached for discuss message %s: %s",
                self.id,
                error,
            )
        except Exception:
            _logger.exception(
                "Assistant backend call failed unexpectedly for discuss message %s",
                self.id,
            )

        return ""
