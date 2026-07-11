from odoo import fields, models


class CmSaDelegationItem(models.Model):
    _name = "cm_sa.delegation.item"
    _description = "Approval Delegation Item"
    _order = "id desc"

    log_id = fields.Many2one(
        "cm_sa.delegation.log",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    original_user_id = fields.Many2one(
        "res.users",
        required=True,
    )
    delegate_user_id = fields.Many2one(
        "res.users",
        required=True,
    )
    reverted = fields.Boolean(default=False, index=True)
    reverted_at = fields.Datetime()
