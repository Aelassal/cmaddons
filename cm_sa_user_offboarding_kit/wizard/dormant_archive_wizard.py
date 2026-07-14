from odoo import _, fields, models


class DormantArchiveWizard(models.TransientModel):
    _name = "cm_sa.dormant.archive.wizard"
    _description = "Archive Dormant Users"

    user_ids = fields.Many2many(
        "res.users",
        string="Users to Archive",
        domain="[('active', '=', True)]",
        required=True,
    )
    reason = fields.Char(
        string="Reason",
        required=True,
        default=lambda self: _("Dormant account — bulk archive"),
    )

    def action_archive(self):
        self.ensure_one()
        protected_ids = self.env["res.users"]._offboarding_protected_user_ids()
        users = self.user_ids.sudo().filtered(
            lambda u: u.id not in protected_ids and u.active
        )
        users._offboarding_archive_users(self.reason, source="dormant wizard")
        return {"type": "ir.actions.act_window_close"}
