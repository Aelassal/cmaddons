from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cm_sa_dedup_threshold = fields.Float(
        string="Duplicate Warning Threshold",
        default=0.8,
        config_parameter="cm_sa_bill_dedup.threshold",
        help="Combined match score (0.0-1.0) at which a warning is shown.",
    )
    cm_sa_dedup_window_days = fields.Integer(
        string="Lookback Window (days)",
        default=90,
        config_parameter="cm_sa_bill_dedup.window_days",
        help="Only compare against bills within this many days.",
    )
    cm_sa_dedup_amount_tolerance = fields.Float(
        string="Amount Tolerance (fraction)",
        default=0.01,
        config_parameter="cm_sa_bill_dedup.amount_tolerance",
        help="Fraction of amount difference still considered 'same amount'. 0.01 = 1%.",
    )
    cm_sa_dedup_date_tolerance_days = fields.Integer(
        string="Date Tolerance (days)",
        default=5,
        config_parameter="cm_sa_bill_dedup.date_tolerance_days",
        help="Max days between two bills still considered 'same date'.",
    )
    cm_sa_dedup_check_amount = fields.Boolean(
        string="Weight Amount Similarity",
        default=True,
        config_parameter="cm_sa_bill_dedup.check_amount",
    )
    cm_sa_dedup_check_date = fields.Boolean(
        string="Weight Date Similarity",
        default=True,
        config_parameter="cm_sa_bill_dedup.check_date",
    )
