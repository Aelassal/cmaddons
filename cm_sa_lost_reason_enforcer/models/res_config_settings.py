# -*- coding: utf-8 -*-
from odoo import fields, models


PARAM_REASON_REQUIRED = "cm_sa_lost_reason_enforcer.reason_required"
PARAM_NOTE_REQUIRED = "cm_sa_lost_reason_enforcer.note_required"
PARAM_NOTE_MIN_CHARS = "cm_sa_lost_reason_enforcer.note_min_chars"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cm_sa_lost_reason_required = fields.Boolean(
        string="Require Lost Reason",
        default=True,
        config_parameter=PARAM_REASON_REQUIRED,
        help=(
            "When enabled, sales reps cannot close the 'Mark as Lost' wizard "
            "without selecting a Lost Reason."
        ),
    )
    cm_sa_lost_note_required = fields.Boolean(
        string="Require Closing Note",
        default=True,
        config_parameter=PARAM_NOTE_REQUIRED,
        help=(
            "When enabled, sales reps must write a closing note before "
            "marking the lead as lost."
        ),
    )
    cm_sa_lost_note_min_chars = fields.Integer(
        string="Minimum Closing Note Length",
        default=10,
        config_parameter=PARAM_NOTE_MIN_CHARS,
        help=(
            "Minimum number of characters required in the closing note "
            "(whitespace and HTML tags are stripped before counting)."
        ),
    )
