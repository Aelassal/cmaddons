from odoo import fields, models


class CmSaPaymentScoreSnapshot(models.Model):
    _name = "cm_sa.payment_score.snapshot"
    _description = "Payment Score Monthly Snapshot"
    _order = "computed_at desc, id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    computed_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    period_year = fields.Integer(required=True, index=True)
    period_month = fields.Integer(required=True, index=True)
    score = fields.Integer(string="Score (0-100)", required=True)
    band = fields.Selection(
        [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        required=True,
        index=True,
    )
    breakdown_json = fields.Text(string="Breakdown (JSON)", readonly=True)

    _snapshot_period_uniq = models.Constraint(
        "unique(partner_id, period_year, period_month)",
        "A payment-score snapshot for this partner already exists for that month.",
    )
