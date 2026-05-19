# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.mail import is_html_empty

from .res_config_settings import (
    PARAM_NOTE_MIN_CHARS,
    PARAM_NOTE_REQUIRED,
    PARAM_REASON_REQUIRED,
)


def _html_to_text(value):
    """Strip tags and collapse whitespace from an HTML field for length checks."""
    if not value:
        return ""
    if is_html_empty(value):
        return ""
    # Strip HTML tags then unescape common entities and collapse whitespace.
    text = re.sub(r"<[^>]+>", "", str(value))
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return text.strip()


class CrmLeadLost(models.TransientModel):
    _inherit = "crm.lead.lost"

    def action_lost_reason_apply(self):
        """Enforce mandatory lost reason and closing note before applying."""
        ICP = self.env["ir.config_parameter"].sudo()
        reason_required = ICP.get_param(PARAM_REASON_REQUIRED, "True")
        note_required = ICP.get_param(PARAM_NOTE_REQUIRED, "True")
        try:
            min_chars = int(ICP.get_param(PARAM_NOTE_MIN_CHARS, "10") or 0)
        except (TypeError, ValueError):
            min_chars = 10

        reason_required = str(reason_required).lower() in ("1", "true", "yes")
        note_required = str(note_required).lower() in ("1", "true", "yes")

        for wizard in self:
            if reason_required and not wizard.lost_reason_id:
                raise UserError(_("Please select a lost reason."))

            note_text = _html_to_text(wizard.lost_feedback)
            if note_required and len(note_text) < min_chars:
                raise UserError(
                    _(
                        "Please add a closing note of at least %s characters."
                    )
                    % min_chars
                )

        # Capture per-wizard data before delegating to super(), so we can post
        # the audit chatter message on each affected lead afterwards.
        wizard_data = []
        for wizard in self:
            wizard_data.append(
                (
                    wizard.lead_ids,
                    wizard.lost_reason_id.name or _("(no reason)"),
                    _html_to_text(wizard.lost_feedback) or _("(no note)"),
                )
            )

        res = super().action_lost_reason_apply()

        # Audit trail: post a chatter message on each affected lead.
        for leads, reason_name, note_text in wizard_data:
            body = Markup(
                "<p><b>%s</b></p><p>%s: %s</p><p>%s: %s</p>"
            ) % (
                _("Marked lost."),
                _("Reason"),
                reason_name,
                _("Note"),
                note_text,
            )
            for lead in leads:
                lead.message_post(body=body)

        return res
