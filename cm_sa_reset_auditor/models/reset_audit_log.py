from odoo import fields, models


class CmSaResetAuditLog(models.Model):
    _name = "cm_sa.reset_audit.log"
    _description = "Reset-to-Draft Audit Log"
    _order = "create_date desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.reset_audit.rule",
        string="Rule",
        ondelete="set null",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_name = fields.Char()
    method_name = fields.Char(required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Reset By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    reason = fields.Text()

    def action_open_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
