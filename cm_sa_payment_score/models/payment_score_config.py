from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CmSaPaymentScoreConfig(models.Model):
    _name = "cm_sa.payment_score.config"
    _description = "Payment Score Configuration"
    _order = "id"

    name = fields.Char(
        required=True,
        default="Default",
        help="Human-readable label for this config row.",
    )
    active = fields.Boolean(default=True)

    window_days = fields.Integer(
        default=90,
        required=True,
        help="Rolling window in days used to score payment behavior.",
    )

    weight_days_late = fields.Integer(
        string="Weight: Avg Days Late",
        default=40,
        required=True,
    )
    weight_partial = fields.Integer(
        string="Weight: Partial-Payment Ratio",
        default=15,
        required=True,
    )
    weight_stretch = fields.Integer(
        string="Weight: Credit-Limit Stretch",
        default=20,
        required=True,
    )
    weight_on_time = fields.Integer(
        string="Weight: On-Time Streak",
        default=25,
        required=True,
    )

    band_a_min = fields.Integer(string="Band A minimum", default=85, required=True)
    band_b_min = fields.Integer(string="Band B minimum", default=70, required=True)
    band_c_min = fields.Integer(string="Band C minimum", default=50, required=True)

    require_rule = fields.Boolean(
        string="Block D-band sale orders",
        default=False,
        help="When enabled, confirming a sale order for a partner with band D "
             "raises a UserError unless the user is a system administrator. "
             "The block is installed at registry load via _register_hook.",
    )

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
                        "Only one active Payment Score configuration is "
                        "allowed at a time. Archive %s first."
                    ) % dup.name)

    @api.constrains(
        "weight_days_late", "weight_partial",
        "weight_stretch", "weight_on_time",
    )
    def _check_weights(self):
        for rec in self:
            total = (
                rec.weight_days_late + rec.weight_partial
                + rec.weight_stretch + rec.weight_on_time
            )
            if total <= 0:
                raise ValidationError(_("The sum of weights must be > 0."))
            for w in (
                rec.weight_days_late, rec.weight_partial,
                rec.weight_stretch, rec.weight_on_time,
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

    @api.constrains("window_days")
    def _check_window(self):
        for rec in self:
            if rec.window_days < 7:
                raise ValidationError(_("Window must be at least 7 days."))

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
