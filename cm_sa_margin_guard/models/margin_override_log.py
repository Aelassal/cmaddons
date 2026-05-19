from odoo import fields, models


class CmSaMarginOverrideLog(models.Model):
    _name = "cm_sa.margin.override.log"
    _description = "Margin Guard Override Log"
    _order = "create_date desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.margin.guard.rule",
        string="Rule",
        ondelete="set null",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_name = fields.Char()
    user_id = fields.Many2one(
        "res.users",
        string="Overridden By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    threshold_pct = fields.Float(string="Threshold %")
    actual_pct = fields.Float(string="Actual Margin %")
    gap_pct = fields.Float(
        string="Gap",
        compute="_compute_gap_pct",
        store=True,
    )
    reason = fields.Text()

    def _compute_gap_pct(self):
        for rec in self:
            rec.gap_pct = (rec.threshold_pct or 0.0) - (rec.actual_pct or 0.0)

    def action_open_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
