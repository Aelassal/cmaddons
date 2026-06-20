from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CmSaDiscountAuditConfig(models.Model):
    """Singleton holding the discount threshold + audit-reason setting.

    Kept as a regular model with a unique record (id=1 created on install
    via a default_get fallback), rather than ir.config_parameter, so the
    config UI is a normal form view visible to sales managers.
    """

    _name = "cm_sa.discount.audit.config"
    _description = "Discount Audit Configuration"
    _order = "id"

    name = fields.Char(default="Discount Audit Settings", required=True)
    threshold_pct = fields.Float(
        string="Audit Threshold %",
        default=15.0,
        required=True,
        help="Any SO line whose discount percentage strictly exceeds this "
             "value writes a row to the audit log. Default: 15%.",
    )
    show_reason_field = fields.Boolean(
        string="Show Reason Field on SO Lines",
        default=True,
        help="When on, a free-text 'Discount Reason' field is shown on each "
             "sale order line. Its value is copied onto the audit-log row "
             "when the discount exceeds the threshold. Not required.",
    )
    post_chatter_on_audit = fields.Boolean(
        string="Post Chatter Note on Audit",
        default=True,
        help="When on, each time an audit row is written a chatter note "
             "lands on the parent sale order. Turn off for low-noise mode.",
    )

    @api.constrains("threshold_pct")
    def _check_threshold(self):
        for rec in self:
            if rec.threshold_pct < 0 or rec.threshold_pct > 100:
                raise ValidationError(_(
                    "Threshold must be between 0 and 100."
                ))

    @api.model
    def get_singleton(self):
        """Return the first (and only) config row, creating it if missing."""
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec
