from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_credit_held = fields.Boolean(
        string="On Credit Hold",
        readonly=True,
        copy=False,
        index=True,
    )
    credit_hold_reason = fields.Text(
        string="Hold Reason",
        readonly=True,
        copy=False,
    )
    credit_hold_applied_at = fields.Datetime(
        string="Hold Applied At",
        readonly=True,
        copy=False,
    )
    credit_hold_applied_by = fields.Many2one(
        "res.users",
        string="Hold Applied By",
        readonly=True,
        copy=False,
    )
    credit_hold_expected_release = fields.Date(
        string="Expected Release",
        readonly=True,
        copy=False,
    )

    def action_open_credit_hold_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Place on Credit Hold"),
            "res_model": "cm_sa.credit_hold.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
                "default_mode": "hold",
            },
        }

    def action_open_credit_release_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Release Credit Hold"),
            "res_model": "cm_sa.credit_hold.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
                "default_mode": "release",
            },
        }
