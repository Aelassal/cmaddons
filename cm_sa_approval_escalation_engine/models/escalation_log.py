from odoo import fields, models


class ApprovalEscalationLog(models.Model):
    _name = "approval.escalation.log"
    _description = "Approval Escalation Log"
    _order = "create_date desc"
    _rec_name = "res_model"

    rule_id = fields.Many2one(
        "approval.escalation.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    step_id = fields.Many2one(
        "approval.escalation.step",
        required=True,
        ondelete="cascade",
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    res_ref = fields.Reference(
        selection="_reference_models",
        compute="_compute_res_ref",
    )
    escalated_to_id = fields.Many2one("res.users")
    body = fields.Html()

    def _reference_models(self):
        return [(m.model, m.name) for m in self.env["ir.model"].sudo().search([])]

    def _compute_res_ref(self):
        for rec in self:
            rec.res_ref = (
                f"{rec.res_model},{rec.res_id}" if rec.res_model and rec.res_id else False
            )
