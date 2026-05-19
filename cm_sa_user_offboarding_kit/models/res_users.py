from datetime import timedelta

from odoo import _, api, fields, models

# Skip admin (1), public (2), portal (3) and __system (4) — these are
# infrastructure accounts, never offboarded.
SYSTEM_USER_IDS = (1, 2, 3, 4)

DORMANT_DAYS_PARAM = "cm_sa_user_offboarding_kit.dormant_days"
DEFAULT_DORMANT_DAYS = 90


class ResUsers(models.Model):
    # res.users already inherits mail.thread in Odoo 19, so no need to add it.
    _inherit = "res.users"

    deactivation_date = fields.Date(
        string="Scheduled Deactivation",
        help="On this date the daily offboarding cron will archive this user "
             "and post the reason to chatter.",
    )
    deactivation_reason = fields.Char(
        string="Deactivation Reason",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _offboarding_dormant_days(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            DORMANT_DAYS_PARAM, DEFAULT_DORMANT_DAYS,
        )
        try:
            days = int(value)
        except (TypeError, ValueError):
            days = DEFAULT_DORMANT_DAYS
        return max(days, 1)

    @api.model
    def _offboarding_dormant_cutoff(self):
        return fields.Datetime.now() - timedelta(
            days=self._offboarding_dormant_days(),
        )

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    @api.model
    def _cron_auto_deactivate_scheduled(self):
        """Archive users whose scheduled deactivation date has arrived."""
        today = fields.Date.context_today(self)
        users = self.sudo().search([
            ("active", "=", True),
            ("deactivation_date", "!=", False),
            ("deactivation_date", "<=", today),
            ("id", "not in", list(SYSTEM_USER_IDS)),
        ])
        for user in users:
            reason = user.deactivation_reason or _("No reason provided")
            user.message_post(body=_(
                "Auto-deactivated on %(date)s: %(reason)s",
                date=today, reason=reason,
            ))
            user.write({"active": False})
        return True

    @api.model
    def _cron_flag_dormant_users(self):
        """Touch dormant users so the Dormant view stays fresh.

        We don't auto-archive — admin must confirm via the wizard. This cron
        exists so the dormant query is materialised on a schedule (and so the
        threshold parameter is read regularly, surfacing config issues).
        """
        cutoff = self._offboarding_dormant_cutoff()
        dormant = self.sudo().search([
            ("active", "=", True),
            ("login", "!=", False),
            ("login_date", "!=", False),
            ("login_date", "<", cutoff),
            ("id", "not in", list(SYSTEM_USER_IDS)),
        ])
        # No-op write loop intentionally avoided — just return the count for
        # cron logs. The Dormant menu uses the same domain at view time.
        return len(dormant)

    # ------------------------------------------------------------------
    # Actions (called from list view button + menu)
    # ------------------------------------------------------------------
    def action_open_dormant_archive_wizard(self):
        # multi-record allowed: called from a list row button or via the
        # selected ids in the list header.
        eligible = self.filtered(lambda u: u.id not in SYSTEM_USER_IDS and u.active)
        return {
            "type": "ir.actions.act_window",
            "name": _("Archive Dormant Users"),
            "res_model": "cm_sa.dormant.archive.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_user_ids": [(6, 0, eligible.ids)],
            },
        }
