from odoo import fields, models


class CmSaReturnReasonCategory(models.Model):
    _name = "cm_sa.return.reason.category"
    _description = "Return Reason Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Char()
    color = fields.Integer(default=0)

    _name_unique = models.Constraint(
        "unique(name)",
        "A return-reason category with this name already exists.",
    )
