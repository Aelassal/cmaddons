from odoo import fields, models


class CmSaAttachmentBypassLog(models.Model):
    _name = "cm_sa.attachment.bypass.log"
    _description = "Attachment Enforcer Bypass Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.attachment.rule", required=True, ondelete="cascade", index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Move",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Bypassed By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    reason = fields.Text()
    attachment_count_at_bypass = fields.Integer(
        help="Attachments present on the move at the moment of bypass.",
    )

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }
