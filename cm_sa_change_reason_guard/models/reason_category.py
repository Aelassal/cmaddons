from odoo import fields, models


class CmSaReasonCategory(models.Model):
    _name = "cm_sa.reason.category"
    _description = "Change Reason Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _name_unique = models.Constraint(
        "unique(name)",
        "A reason category with this name already exists.",
    )
