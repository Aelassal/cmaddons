from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    cm_sa_timesheet_bypass_reason = fields.Text(
        string="Timesheet Bypass Reason",
        copy=False,
        help=(
            "Temporary reason used when a bypass-group user edits or creates "
            "a locked/back-dated timesheet entry. The value is copied to the "
            "Bypass Log and then cleared from the timesheet line."
        ),
    )
