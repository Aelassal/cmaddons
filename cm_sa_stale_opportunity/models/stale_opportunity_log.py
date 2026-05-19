from odoo import fields, models


class CmSaStaleOpportunityLog(models.Model):
    _name = "cm_sa.stale.opportunity.log"
    _description = "Stale Opportunity Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.stale.opportunity.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lead_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        ondelete="set null",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        ondelete="set null",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        ondelete="set null",
    )
    action = fields.Selection(
        [("warned", "Warned"), ("closed", "Closed")],
        required=True,
        index=True,
    )
    reference_date = fields.Datetime(
        help="The stale-reference timestamp on the opportunity at the moment "
             "of this action. Used to dedupe repeat warnings.",
    )

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
