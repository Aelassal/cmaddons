from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CmSaVendorScorecardConfig(models.Model):
    _name = "cm_sa.vendor_scorecard.config"
    _description = "Vendor Scorecard Configuration"
    _order = "id"

    name = fields.Char(required=True, default="Default")
    active = fields.Boolean(default=True)

    window_days = fields.Integer(
        default=180,
        required=True,
        help="Rolling window in days used for scoring receipts and prices.",
    )
    price_reference_days = fields.Integer(
        default=180,
        required=True,
        help="Window in days used to compute the baseline price for the "
             "price-variance metric. Default 6 months.",
    )

    weight_on_time = fields.Integer(
        string="Weight: On-Time %",
        default=45,
        required=True,
    )
    weight_price_variance = fields.Integer(
        string="Weight: Price Variance %",
        default=30,
        required=True,
    )
    weight_bill_dispute = fields.Integer(
        string="Weight: Bill Disputes",
        default=25,
        required=True,
    )

    band_a_min = fields.Integer(string="Band A minimum", default=85, required=True)
    band_b_min = fields.Integer(string="Band B minimum", default=70, required=True)
    band_c_min = fields.Integer(string="Band C minimum", default=50, required=True)

    @api.constrains("active")
    def _check_one_active(self):
        for rec in self:
            if rec.active:
                dup = self.search([
                    ("active", "=", True),
                    ("id", "!=", rec.id),
                ], limit=1)
                if dup:
                    raise ValidationError(_(
                        "Only one active Vendor Scorecard configuration is "
                        "allowed at a time. Archive %s first."
                    ) % dup.name)

    @api.constrains(
        "weight_on_time", "weight_price_variance", "weight_bill_dispute",
    )
    def _check_weights(self):
        for rec in self:
            total = (
                rec.weight_on_time + rec.weight_price_variance
                + rec.weight_bill_dispute
            )
            if total <= 0:
                raise ValidationError(_("The sum of weights must be > 0."))
            for w in (
                rec.weight_on_time, rec.weight_price_variance,
                rec.weight_bill_dispute,
            ):
                if w < 0:
                    raise ValidationError(_("Weights must be >= 0."))

    @api.constrains("band_a_min", "band_b_min", "band_c_min")
    def _check_bands(self):
        for rec in self:
            if not (0 <= rec.band_c_min < rec.band_b_min < rec.band_a_min <= 100):
                raise ValidationError(_(
                    "Band cutoffs must satisfy 0 <= C < B < A <= 100."
                ))

    @api.constrains("window_days", "price_reference_days")
    def _check_windows(self):
        for rec in self:
            if rec.window_days < 7:
                raise ValidationError(_("Window must be at least 7 days."))
            if rec.price_reference_days < 7:
                raise ValidationError(_("Price reference window must be at least 7 days."))

    @api.model
    def _get_active(self):
        rec = self.search([("active", "=", True)], limit=1)
        if not rec:
            rec = self.search([], limit=1)
        return rec

    def band_for_score(self, score):
        self.ensure_one()
        if score >= self.band_a_min:
            return "A"
        if score >= self.band_b_min:
            return "B"
        if score >= self.band_c_min:
            return "C"
        return "D"
