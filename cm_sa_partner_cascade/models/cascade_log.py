from odoo import fields, models


class CmSaCascadeLog(models.Model):
    _name = "cm_sa.cascade.log"
    _description = "Partner Cascade Log"
    _order = "applied_at desc, id desc"
    _rec_name = "parent_id"

    parent_id = fields.Many2one(
        "res.partner",
        string="Parent Partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    applied_by = fields.Many2one(
        "res.users",
        string="Applied By",
        required=True,
        default=lambda self: self.env.user.id,
    )
    applied_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    changes = fields.Text(
        help="JSON blob of {field: {old, new}} applied during this cascade.",
    )
    count_applied = fields.Integer(
        string="# Children Updated",
        default=0,
    )
