from odoo import fields, models


class CmSaDelegationLog(models.Model):
    _name = "cm_sa.delegation.log"
    _description = "Approval Delegation Log"
    _order = "started_at desc, id desc"
    _rec_name = "from_user_id"

    from_user_id = fields.Many2one(
        "res.users",
        string="From User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    to_user_id = fields.Many2one(
        "res.users",
        string="Delegate",
        required=True,
        ondelete="cascade",
    )
    started_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    ended_at = fields.Datetime(readonly=True)
    reassigned_activity_count = fields.Integer(default=0)
    reassigned_approval_count = fields.Integer(default=0)
    auto_reversed = fields.Boolean(default=False)
    item_ids = fields.One2many(
        "cm_sa.delegation.item",
        "log_id",
        string="Reassignments",
    )
