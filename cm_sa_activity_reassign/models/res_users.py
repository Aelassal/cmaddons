from odoo import _, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def action_open_activity_reassign_wizard(self):
        """Open the bulk activity reassignment wizard from a user form.

        The current user is used as the source user, so administrators can
        quickly move all open activities owned by that user to another user.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reassign Activities"),
            "res_model": "cm_sa.activity.reassign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                **self.env.context,
                "default_from_user_id": self.id,
            },
        }
