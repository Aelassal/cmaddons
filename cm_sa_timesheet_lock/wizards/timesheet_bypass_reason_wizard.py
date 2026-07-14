from odoo import _, fields, models
from odoo.exceptions import UserError

CTX_BYPASS = "cm_sa_timesheet_lock_bypass"
REASON_FIELD = "cm_sa_timesheet_bypass_reason"


class CmSaTimesheetBypassReasonWizard(models.TransientModel):
    _name = "cm_sa.timesheet.lock.bypass.wizard"
    _description = "Timesheet Lock Bypass Reason Wizard"

    line_ids = fields.Many2many(
        "account.analytic.line",
        string="Timesheet Entries",
        required=True,
        default=lambda self: self._default_line_ids(),
    )
    reason = fields.Text(
        string="Bypass Reason",
        required=True,
        help="Mandatory reason that will be used once when saving a locked timesheet entry.",
    )

    def _default_line_ids(self):
        if self.env.context.get("active_model") == "account.analytic.line":
            return self.env.context.get("active_ids", [])
        return []

    def action_apply_reason(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("Please enter a bypass reason."))
        if not self.line_ids:
            raise UserError(_("Please select at least one timesheet entry."))

        # Store the reason temporarily on the selected lines. The create/write
        # guard will copy it to the Bypass Log and clear it after the real edit.
        self.line_ids.with_context(**{CTX_BYPASS: True}).write({
            REASON_FIELD: reason,
        })
        return {"type": "ir.actions.act_window_close"}
