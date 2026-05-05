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
        if self.env.context.get("skip_virtual_assistant_followup"):
            _logger.info(
                "Skipping discuss follow-up for message %s because it was posted by the assistant flow.",
                self.id,
            )
            return
        if self.message_type != "comment":
            _logger.info(
                "Skipping discuss follow-up for message %s because message_type=%s is not a user comment.",
                self.id,
                self.message_type,
            )
            return
        if not self.author_id:
            _logger.info(
                "Skipping discuss follow-up for message %s because no author_id is present.",
                self.id,
            )
            return
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
            "ticket_description": ticket.description or "" if ticket else "",
            "ticket_partner_name": self._get_related_name(ticket, "partner_id"),
            "ticket_partner_email": ticket.partner_id.email if ticket and ticket.partner_id else "",
            "ticket_team": self._get_related_name(ticket, "team_id"),
            "ticket_category": self._get_related_name(ticket, "category_id"),
            "ticket_type": self._get_related_name(ticket, "type_id"),
            "ticket_stage": self._get_related_name(ticket, "stage_id"),
            "assistant_route_name": ticket.assistant_route_name or "",
            "channel_id": channel.id,
            "channel_name": channel.name or "",
            "message_id": self.id,
            "author_name": self.author_id.name if self.author_id else "",
            "author_email": self.author_id.email if self.author_id else "",
            "body": body_text,
            "recent_messages": self._get_recent_channel_messages(channel),
            "thread_id": f"odoo-discuss-{channel.id}",
        }

        backend_result = self._fetch_virtual_assistant_followup(payload)
        reply_text = str(backend_result.get("reply_text", "")).strip()
        actions = backend_result.get("actions", []) or []
        if not reply_text and not actions:
            _logger.info("Assistant backend returned no follow-up work for discuss message %s", self.id)
            return

        if reply_text:
            _logger.info(
                "Posting assistant follow-up to channel %s for discuss message %s using route backend",
                channel.id,
                self.id,
            )
            channel.with_context(skip_virtual_assistant_followup=True).with_user(assistant_user).message_post(
                body=reply_text,
                author_id=assistant_user.partner_id.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

        if actions:
            self._apply_virtual_assistant_actions(actions, ticket)

    def _get_virtual_assistant_channel(self):
        self.ensure_one()
        model_name = self.model or ""
        if not self.res_id:
            return False

        if model_name not in {"discuss.channel", "mail.channel"}:
            return False

        channel = self.env["discuss.channel"].sudo().browse(self.res_id)
        if channel.exists() and channel.name and _CHANNEL_NAME_PATTERN.match(channel.name):
            return channel
        return False

    def _extract_plain_body(self):
        self.ensure_one()
        body = self.body or ""
        plain_body = re.sub(r"<[^>]+>", " ", body)
        plain_body = re.sub(r"\s+", " ", plain_body).strip()
        return plain_body

    def _get_recent_channel_messages(self, channel, limit=8):
        self.ensure_one()
        messages = self.env["mail.message"].sudo().search(
            [
                ("model", "in", ["discuss.channel", "mail.channel"]),
                ("res_id", "=", channel.id),
                ("message_type", "=", "comment"),
            ],
            order="id desc",
            limit=limit,
        )
        result = []
        for message in reversed(messages):
            result.append(
                {
                    "id": message.id,
                    "author_name": message.author_id.name if message.author_id else "",
                    "author_email": message.author_id.email if message.author_id else "",
                    "body": message._extract_plain_body(),
                    "date": str(message.date or ""),
                }
            )
        return result

    @staticmethod
    def _get_related_name(record, field_name):
        if not record or field_name not in record._fields:
            return ""
        related = record[field_name]
        return related.name if related else ""

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
            with urlopen(request, timeout=60) as response:
                raw_body = response.read().decode("utf-8")
            parsed = json.loads(raw_body)
            if not isinstance(parsed, dict):
                _logger.warning(
                    "Assistant backend returned an unexpected response for discuss message %s.",
                    self.id,
                )
                return {}
            reply_text = str(parsed.get("reply_text", "")).strip()
            actions = parsed.get("actions", []) or []
            if reply_text or actions:
                return parsed
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

        return {}

    def _apply_virtual_assistant_actions(self, actions, ticket):
        self.ensure_one()
        if not isinstance(actions, list):
            _logger.warning("Ignoring malformed assistant actions for discuss message %s: %s", self.id, actions)
            return

        for action in actions:
            if not isinstance(action, dict):
                _logger.warning("Ignoring malformed assistant action for discuss message %s: %s", self.id, action)
                continue

            action_type = action.get("type")
            if action_type != "mark_ticket_ready":
                _logger.info("Ignoring unsupported assistant action for discuss message %s: %s", self.id, action_type)
                continue

            action_ticket = ticket if ticket and ticket.exists() else False
            try:
                action_ticket_id = int(action.get("ticket_id") or 0)
            except (TypeError, ValueError):
                action_ticket_id = 0
            if action_ticket and action_ticket_id and int(action_ticket_id) != action_ticket.id:
                _logger.warning(
                    "Ignoring mark_ticket_ready for ticket %s from channel ticket %s",
                    action_ticket_id,
                    action_ticket.id,
                )
                continue
            if not action_ticket and action_ticket_id:
                action_ticket = self.env["helpdesk.ticket"].sudo().browse(int(action_ticket_id))
            if not action_ticket or not action_ticket.exists():
                _logger.warning("Cannot apply mark_ticket_ready because ticket was not found: %s", action_ticket_id)
                continue
            if action_ticket.kanban_state == "done":
                _logger.info("Ticket %s is already Ready for next stage", action_ticket.id)
                continue

            _logger.info("Marking ticket %s as Ready for next stage from assistant chat confirmation", action_ticket.id)
            action_ticket.sudo().write({"kanban_state": "done"})
