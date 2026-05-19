import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class CmSaDormantLog(models.Model):
    _name = "cm_sa.dormant.log"
    _description = "Dormant User Log"
    _order = "create_date desc, id desc"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="restrict",
        index=True,
    )
    user_login = fields.Char(
        related="user_id.login", store=True, readonly=True,
    )
    user_active = fields.Boolean(
        related="user_id.active", store=False, readonly=True,
    )
    action = fields.Selection(
        [
            ("warned", "Warned"),
            ("archived", "Archived"),
            ("reactivated", "Reactivated"),
        ],
        required=True,
        index=True,
    )
    days_inactive = fields.Integer()
    login_date_at_action = fields.Datetime(
        string="Login Date at Action",
        help="Value of user.login_date at the time of this action — used to "
             "dedupe repeat warnings.",
    )

    def action_reactivate(self):
        """Reactivate the linked user and write a log row."""
        for rec in self:
            if not rec.user_id:
                continue
            if rec.user_id.active:
                continue
            try:
                rec.user_id.sudo().write({"active": True})
            except Exception:
                _logger.exception(
                    "DormantUser: reactivate failed for user %s", rec.user_id.id,
                )
                continue
            self.sudo().create({
                "user_id": rec.user_id.id,
                "action": "reactivated",
                "days_inactive": 0,
            })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reactivated"),
                "message": _("%s user(s) reactivated.") % len(self),
                "type": "success",
                "sticky": False,
            },
        }
