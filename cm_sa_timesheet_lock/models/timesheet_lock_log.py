from odoo import _, fields, models


class CmSaTimesheetLockLog(models.Model):
    _name = "cm_sa.timesheet.lock.log"
    _description = "Timesheet Lock Bypass Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.timesheet.lock.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    timesheet_id = fields.Many2one(
        "account.analytic.line",
        string="Timesheet Entry",
        ondelete="set null",
        index=True,
    )
    entry_date = fields.Date(
        string="Back-Dated Entry Date",
        help="The date of the timesheet entry that was overridden.",
    )
    window_days = fields.Integer(string="Window (days)")
    source = fields.Selection(
        [
            ("create", "Create"),
            ("write-new-date", "Write (new date)"),
            ("write-same-date", "Write (existing date)"),
        ],
        required=True,
    )
    reason = fields.Text(
        string="Bypass Reason",
        required=True,
        default=lambda self: _("Legacy bypass — reason was not captured."),
        help="Mandatory justification entered by the bypass user.",
    )
