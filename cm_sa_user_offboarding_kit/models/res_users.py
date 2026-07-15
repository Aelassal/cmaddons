import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Technical accounts are resolved dynamically by XML ID.
# Do not hard-code user IDs because customer databases may have normal
# internal test users with IDs 3 or 4. Hard-coding those IDs caused
# scheduled deactivation to silently skip valid users in Odoo 19 databases.
PROTECTED_USER_XMLIDS = (
    "base.user_root",      # OdooBot / superuser
    "base.user_admin",     # main administrator
    "base.public_user",    # public website user
    "base.default_user",   # template/default user, when present
    "base.user_demo",      # demo user, when present
)

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
    def _offboarding_protected_user_ids(self):
        """Return technical users that must never be archived automatically.

        The previous implementation used a fixed tuple (1, 2, 3, 4).
        That is unsafe on real/test databases because normal users may have
        those IDs. Resolve the protected accounts by XML ID instead.
        """
        protected = set()
        for xmlid in PROTECTED_USER_XMLIDS:
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user and user._name == "res.users":
                protected.add(user.id)
        return list(protected)

    def _offboarding_post_audit_note(self, body):
        """Post an audit note where available without blocking archiving.

        Some Odoo 19 builds do not expose mail.thread/message_post on
        res.users. In that case, use the related partner chatter. If even
        that fails, keep the offboarding action working and write to the
        server log instead.
        """
        for user in self.sudo().with_context(active_test=False):
            try:
                target = user
                if not callable(getattr(target, "message_post", None)):
                    target = user.partner_id if user.partner_id else False
                if target and callable(getattr(target, "message_post", None)):
                    with self.env.cr.savepoint():
                        target.message_post(body=body)
                else:
                    _logger.info(
                        "UserOffboarding audit note for %s: %s",
                        user.login or user.name,
                        body,
                    )
            except Exception:
                _logger.exception(
                    "UserOffboarding: failed to post audit note for user %s",
                    user.login or user.name,
                )

    def _offboarding_archive_users(self, reason, source="scheduled"):
        """Archive users and leave a best-effort audit note first."""
        today = fields.Date.today()
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        protected_ids = set(Users._offboarding_protected_user_ids())
        users = self.sudo().with_context(active_test=False).filtered(
            lambda u: bool(u.active) and u.id not in protected_ids
        )
        for user in users:
            body = _(
                "User archived by User Offboarding Kit. "
                "Source: %(source)s. Date: %(date)s. Reason: %(reason)s"
            ) % {
                "source": source,
                "date": today,
                "reason": reason or _("No reason provided"),
            }
            user._offboarding_post_audit_note(body)
        if users:
            users.write({"active": False})
        return len(users)

    @api.model
    def _scheduled_deactivation_domain(self):
        """Domain used by the scheduled offboarding cron.

        Having it in one method makes troubleshooting easier from Odoo shell.
        """
        today = fields.Date.today()
        return [
            ("active", "=", True),
            ("deactivation_date", "!=", False),
            ("deactivation_date", "<=", today),
            ("id", "not in", self._offboarding_protected_user_ids()),
        ]

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
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        users = Users.search(Users._scheduled_deactivation_domain())
        count = 0
        for user in users:
            count += user._offboarding_archive_users(
                user.deactivation_reason or _("No reason provided"),
                source="scheduled",
            )
        _logger.info(
            "UserOffboarding: scheduled deactivation found %s eligible user(s), archived %s user(s): %s",
            len(users), count, ", ".join(users.mapped("login")) or "none",
        )
        return count

    @api.model
    def _cron_flag_dormant_users(self):
        """Touch dormant users so the Dormant view stays fresh.

        We don't auto-archive — admin must confirm via the wizard. This cron
        exists so the dormant query is materialised on a schedule (and so the
        threshold parameter is read regularly, surfacing config issues).
        """
        cutoff = self._offboarding_dormant_cutoff()
        dormant = self.sudo().with_context(active_test=False).search([
            ("active", "=", True),
            ("login", "!=", False),
            ("login_date", "!=", False),
            ("login_date", "<", cutoff),
            ("id", "not in", self._offboarding_protected_user_ids()),
        ])
        # No-op write loop intentionally avoided — just return the count for
        # cron logs. The Dormant menu uses the same domain at view time.
        return len(dormant)

    # ------------------------------------------------------------------
    # Actions (called from list view button + menu)
    # ------------------------------------------------------------------

    def action_offboarding_archive_now(self):
        """Manual button from the user form for immediate verification.

        This is intentionally restricted by the view to Settings users.
        It uses the same safe archiving path as the cron.
        """
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        protected_ids = set(Users._offboarding_protected_user_ids())
        for user in self.sudo().with_context(active_test=False):
            if user.id in protected_ids:
                raise UserError(_("This technical/admin user is protected and cannot be archived automatically."))
            if not user.active:
                continue
            user._offboarding_archive_users(
                user.deactivation_reason or _("Manual offboarding"),
                source="manual",
            )
        return {"type": "ir.actions.client", "tag": "reload"}
    def action_open_dormant_archive_wizard(self):
        # multi-record allowed: called from a list row button or via the
        # selected ids in the list header.
        protected_ids = self._offboarding_protected_user_ids()
        eligible = self.filtered(lambda u: u.id not in protected_ids and u.active)
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
