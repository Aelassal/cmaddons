from odoo import fields, models


class CmSaRenewalLog(models.Model):
    _name = "cm_sa.renewal.log"
    _description = "Renewal Pipeline Log"
    _order = "create_date desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.renewal.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_name = fields.Char()
    end_date = fields.Date(required=True, index=True)
    lead_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        ondelete="set null",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        ondelete="set null",
    )
    expected_revenue = fields.Float(
        string="Expected Revenue",
        digits=(16, 2),
    )
    quote_template_id = fields.Many2one(
        "sale.order.template",
        string="Renewal Quote Template",
        ondelete="set null",
    )

    _idempotent = models.Constraint(
        "unique(rule_id, res_model, res_id, end_date)",
        "This rule has already created a renewal opportunity for this record and end-date.",
    )

    def action_open_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_lead(self):
        self.ensure_one()
        if not self.lead_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
            "target": "current",
        }
