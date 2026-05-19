import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CmSaDormantConfig(models.Model):
    _name = "cm_sa.dormant.config"
    _description = "Dormant User Auto-Disabler Configuration"
    _order = "id"

    name = fields.Char(default="Dormant User Settings", required=True)
    active = fields.Boolean(default=True)

    inactivity_days = fields.Integer(
        default=90,
        required=True,
        help="Users with a login_date older than this many days are disabled.",
    )
    warning_days = fields.Integer(
        default=7,
        required=True,
        help="Days before disable to email the user + admin group. 0 to skip.",
    )
    exclude_group_ids = fields.Many2many(
        "res.groups",
        "cm_sa_dormant_exclude_group_rel",
        "config_id", "group_id",
        string="Always-Active Groups",
        help="Users in any of these groups are never disabled, no matter "
             "how long they've been inactive. Typical: administrators, "
             "service accounts, always-on integration users.",
    )
    notify_group_id = fields.Many2one(
        "res.groups",
        string="Admin Notify Group",
        help="Members of this group receive warning + disable summaries. "
             "Typical: Settings → Administration / Administrator.",
    )
    license_rate_usd = fields.Float(
        default=30.0,
        help="Monthly USD cost per active user. Used in the ROI "
             "'license savings' number on this form. Purely informational.",
    )
    auto_archive = fields.Boolean(
        default=True,
        help="When off, the cron only sends warning emails and logs them — "
             "it never archives. Use 'dry run' mode to preview behaviour.",
    )

    last_run = fields.Datetime(readonly=True)
    archived_this_month = fields.Integer(compute="_compute_roi_stats")
    estimated_savings_usd = fields.Float(compute="_compute_roi_stats")
    warned_this_month = fields.Integer(compute="_compute_roi_stats")

    def _compute_roi_stats(self):
        Log = self.env["cm_sa.dormant.log"].sudo()
        from datetime import datetime
        now = fields.Datetime.now()
        month_start = datetime(now.year, now.month, 1)
        for rec in self:
            archived = Log.search_count([
                ("create_date", ">=", month_start),
                ("action", "=", "archived"),
            ])
            warned = Log.search_count([
                ("create_date", ">=", month_start),
                ("action", "=", "warned"),
            ])
            rec.archived_this_month = archived
            rec.warned_this_month = warned
            rec.estimated_savings_usd = archived * (rec.license_rate_usd or 0.0)

    @api.constrains("inactivity_days", "warning_days")
    def _check_days(self):
        for rec in self:
            if rec.inactivity_days <= 0:
                raise ValidationError(_("Inactivity Days must be > 0."))
            if rec.warning_days < 0:
                raise ValidationError(_("Warning Days must be >= 0."))
            if rec.warning_days >= rec.inactivity_days:
                raise ValidationError(_(
                    "Warning Days must be less than Inactivity Days."
                ))

    @api.model
    def get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    def _candidate_domain(self):
        self.ensure_one()
        return [
            ("active", "=", True),
            ("share", "=", False),
            ("login_date", "!=", False),
        ]

    def _is_protected(self, user):
        self.ensure_one()
        # Never touch superuser (uid 1)
        if user.id == 1:
            return True
        if not self.exclude_group_ids:
            return False
        return bool(user.groups_id & self.exclude_group_ids)

    def _run_scan(self):
        self.ensure_one()
        Log = self.env["cm_sa.dormant.log"].sudo()
        Users = self.env["res.users"].sudo()
        now = fields.Datetime.now()
        disable_cutoff = now - timedelta(days=self.inactivity_days)
        warn_cutoff = now - timedelta(
            days=max(self.inactivity_days - self.warning_days, 0)
        )

        candidates = Users.search(self._candidate_domain())

        disabled = 0
        warned = 0
        for user in candidates:
            if self._is_protected(user):
                continue
            last_login = user.login_date
            if not last_login:
                continue
            days_inactive = (now - last_login).days

            if last_login <= disable_cutoff and self.auto_archive:
                # Disable + log
                try:
                    user.sudo().write({"active": False})
                except Exception:
                    _logger.exception(
                        "DormantUser: archive failed for user %s", user.id,
                    )
                    continue
                Log.create({
                    "user_id": user.id,
                    "action": "archived",
                    "days_inactive": days_inactive,
                    "login_date_at_action": last_login,
                })
                disabled += 1
                self._notify_archived(user, days_inactive)
            elif (self.warning_days
                  and last_login <= warn_cutoff
                  and last_login > disable_cutoff):
                # Warn, unless already warned for this login_date
                already = Log.search_count([
                    ("user_id", "=", user.id),
                    ("action", "=", "warned"),
                    ("login_date_at_action", "=", last_login),
                ])
                if already:
                    continue
                Log.create({
                    "user_id": user.id,
                    "action": "warned",
                    "days_inactive": days_inactive,
                    "login_date_at_action": last_login,
                })
                warned += 1
                self._notify_warning(user, days_inactive)

        self.write({"last_run": fields.Datetime.now()})
        return (disabled, warned)

    def _notify_warning(self, user, days_inactive):
        self.ensure_one()
        partners = []
        if user.partner_id:
            partners.append(user.partner_id.id)
        if self.notify_group_id:
            partners += [
                u.partner_id.id for u in self.notify_group_id.users
                if u.partner_id
            ]
        partners = list(dict.fromkeys(partners))
        if not partners:
            return
        remaining = max(self.inactivity_days - days_inactive, 0)
        body = _(
            "<p>Odoo user <b>%(name)s</b> (%(login)s) has been inactive for "
            "<b>%(days)s day(s)</b>. Unless they log in, their account will be "
            "disabled in <b>%(remaining)s day(s)</b>.</p>"
            "<p>To keep the account active, log in or ask the admin to add "
            "this user to an Always-Active group.</p>"
        ) % {
            "name": user.name or "",
            "login": user.login or "",
            "days": days_inactive,
            "remaining": remaining,
        }
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Dormant User Warning] %s") % (user.login or user.name),
                "body_html": body,
                "recipient_ids": [(6, 0, partners)],
                "author_id": self.env.user.partner_id.id,
            }).send()
        except Exception:
            _logger.exception("DormantUser: mail send failed")

    def _notify_archived(self, user, days_inactive):
        self.ensure_one()
        if not self.notify_group_id:
            return
        partners = [
            u.partner_id.id for u in self.notify_group_id.users
            if u.partner_id
        ]
        if not partners:
            return
        body = _(
            "<p>Odoo user <b>%(name)s</b> (%(login)s) has been "
            "<b>auto-disabled</b> after %(days)s day(s) of inactivity.</p>"
            "<p>Estimated monthly license saving: "
            "<b>$%(savings).2f</b>.</p>"
        ) % {
            "name": user.name or "",
            "login": user.login or "",
            "days": days_inactive,
            "savings": self.license_rate_usd or 0.0,
        }
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Dormant User Archived] %s") % (user.login or user.name),
                "body_html": body,
                "recipient_ids": [(6, 0, partners)],
                "author_id": self.env.user.partner_id.id,
            }).send()
        except Exception:
            _logger.exception("DormantUser: mail send failed")

    @api.model
    def _cron_scan(self):
        for cfg in self.search([("active", "=", True)]):
            try:
                cfg._run_scan()
            except Exception:
                _logger.exception("DormantUser cron failed for config %s", cfg.id)

    def action_run_now(self):
        self.ensure_one()
        disabled, warned = self._run_scan()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Dormant User Scan"),
                "message": _("Disabled: %(d)s · Warned: %(w)s") % {
                    "d": disabled, "w": warned,
                },
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dormant User Log"),
            "res_model": "cm_sa.dormant.log",
            "view_mode": "list,form",
        }
