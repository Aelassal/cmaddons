from odoo import fields, models


class CmSaAttachmentSizeLog(models.Model):
    _name = "cm_sa.attachment.size.log"
    _description = "Attachment Size Bypass Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.attachment.size.rule",
        required=True, ondelete="cascade", index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer()
    user_id = fields.Many2one(
        "res.users",
        string="Bypassed By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    attachment_name = fields.Char()
    size_mb = fields.Float(string="Size (MB)")
    limit_mb = fields.Float(string="Limit (MB)")
