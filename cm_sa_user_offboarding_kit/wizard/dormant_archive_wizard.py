from odoo import _, fields, models

from ..models.res_users import SYSTEM_USER_IDS


class DormantArchiveWizard(models.TransientModel):
    _name = "cm_sa.dormant.archive.wizard"
    _description = "Archive Dormant Users"

    user_ids = fields.Many2many(
        "res.users",
        string="Users to Archive",
        domain="[('active', '=', True), ('id', 'not in', %s)]" % list(SYSTEM_USER_IDS),
        required=True,
    )
    reason = fields.Char(
        string="Reason",
        required=True,
        default=lambda self: _("Dormant account — bulk archive"),
    )

    def action_archive(self):
        self.ensure_one()
        users = self.user_ids.filtered(
            lambda u: u.id not in SYSTEM_USER_IDS and u.active
        )
        for user in users:
            user.message_post(body=_(
                "Archived via Dormant Users wizard: %(reason)s",
                reason=self.reason,
            ))
        users.write({"active": False})
        return {"type": "ir.actions.act_window_close"}
