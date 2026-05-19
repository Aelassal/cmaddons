from odoo import fields, models


class CmSaVendorScorecardSnapshot(models.Model):
    _name = "cm_sa.vendor_scorecard.snapshot"
    _description = "Vendor Scorecard Snapshot"
    _order = "computed_at desc, id desc"
    _rec_name = "vendor_id"

    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
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
    period_start = fields.Date(required=True, index=True)
    period_end = fields.Date(required=True, index=True)
    score = fields.Integer(string="Score (0-100)", required=True)
    band = fields.Selection(
        [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        required=True,
        index=True,
    )

    on_time_pct = fields.Float(string="On-Time %", digits=(6, 2))
    avg_days_late = fields.Float(string="Avg Days Late", digits=(6, 2))
    price_variance_pct = fields.Float(string="Price Variance %", digits=(6, 2))
    bill_dispute_count = fields.Integer(string="Bill Disputes")
    receipt_count = fields.Integer(string="Receipts Counted")

    breakdown_json = fields.Text(readonly=True)
