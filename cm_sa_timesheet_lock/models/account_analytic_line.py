from odoo import _, fields, models


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

    def action_open_timesheet_bypass_reason_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Enter Bypass Reason"),
            "res_model": "cm_sa.timesheet.lock.bypass.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": self._name,
                "active_ids": self.ids,
            },
        }
