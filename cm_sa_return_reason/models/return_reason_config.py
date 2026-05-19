from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CmSaReturnReasonConfig(models.Model):
    """Singleton holding enforcement settings."""

    _name = "cm_sa.return.reason.config"
    _description = "Return Reason Configuration"
    _order = "id"

    name = fields.Char(default="Return Reason Settings", required=True)
    active = fields.Boolean(default=True)
    min_reason_length = fields.Integer(
        default=10,
        required=True,
        help="Minimum characters required in the typed reason. Set to 0 to "
             "disable the length check.",
    )
    require_category = fields.Boolean(
        default=False,
        help="When on, users must also pick a Reason Category from the "
             "dropdown in addition to typing the free-text reason.",
    )
    post_chatter_note = fields.Boolean(
        default=True,
        help="When on, a chatter note is posted on the source picking every "
             "time a return is created, with the reason + category.",
    )

    @api.constrains("min_reason_length")
    def _check_min_length(self):
        for rec in self:
            if rec.min_reason_length < 0:
                raise ValidationError(_("Min Reason Length must be >= 0."))

    @api.model
    def get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec
