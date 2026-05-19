import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# Keys always treated as sensitive even if the admin hasn't explicitly added
# them to the watch list. Change → instant email alert.
DEFAULT_SENSITIVE_KEYS = [
    "web.base.url",
    "auth.signup.allowed",
    "auth.signup.uninvited",
    "mail.catchall.domain",
    "mail.bounce.alias",
    "mail.catchall.alias",
    "database.expiration_date",
    "database.enterprise_code",
    "database.uuid",
    "report.url",
    "web.base.url.freeze",
    "sentry.dsn",
]


class CmSaConfigAuditorSettings(models.Model):
    """Singleton for auditor configuration."""

    _name = "cm_sa.config_auditor.settings"
    _description = "Config Auditor Settings"
    _order = "id"

    name = fields.Char(default="Config Auditor Settings", required=True)
    active = fields.Boolean(default=True)
    notify_group_id = fields.Many2one(
        "res.groups",
        string="Notify Group",
        help="Members of this group receive immediate email alerts on "
             "sensitive-key changes plus the weekly digest.",
    )
    extra_sensitive_keys = fields.Text(
        string="Extra Sensitive Keys",
        help="One key per line. These will trigger immediate email alerts "
             "in addition to the built-in list (web.base.url, "
             "auth.signup.allowed, etc.).",
    )
    send_weekly_digest = fields.Boolean(
        default=True,
        help="When on, a weekly digest of all changes (not just sensitive) "
             "is emailed to the notify group.",
    )
    alert_on_sensitive = fields.Boolean(
        default=True,
        help="When on, sensitive-key changes trigger an immediate email.",
    )
    log_count = fields.Integer(compute="_compute_log_count")

    def _compute_log_count(self):
        count = self.env["cm_sa.config.change.log"].sudo().search_count([])
        for rec in self:
            rec.log_count = count

    @api.model
    def get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    def _sensitive_key_set(self):
        self.ensure_one()
        keys = set(DEFAULT_SENSITIVE_KEYS)
        if self.extra_sensitive_keys:
            for line in self.extra_sensitive_keys.splitlines():
                k = line.strip()
                if k:
                    keys.add(k)
        return keys

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Config Change Log"),
            "res_model": "cm_sa.config.change.log",
            "view_mode": "list,form",
        }

    @api.model
    def _cron_weekly_digest(self):
        """Emit a weekly digest of logged changes."""
        cfg = self.sudo().get_singleton()
        if not cfg.active or not cfg.send_weekly_digest:
            return
        if not cfg.notify_group_id or not cfg.notify_group_id.users:
            return
        from datetime import timedelta
        since = fields.Datetime.now() - timedelta(days=7)
        Log = self.env["cm_sa.config.change.log"].sudo()
        logs = Log.search([("create_date", ">=", since)], order="create_date desc")
        if not logs:
            return
        partners = [u.partner_id.id for u in cfg.notify_group_id.users if u.partner_id]
        if not partners:
            return
        rows = [
            "<table border='1' cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse;font-family:sans-serif;font-size:12px;'>",
            "<thead><tr style='background:#f2f5f9;'>"
            "<th>When</th><th>User</th><th>Key</th><th>Change</th>"
            "</tr></thead><tbody>",
        ]
        for log in logs[:200]:
            rows.append(
                f"<tr><td>{log.create_date}</td>"
                f"<td>{log.user_id.name if log.user_id else ''}</td>"
                f"<td><code>{log.key}</code></td>"
                f"<td>{log.change_type} — {(log.new_value or '')[:80]}</td></tr>"
            )
        rows.append("</tbody></table>")
        if len(logs) > 200:
            rows.append(
                _("<p>+ %d more changes. Open the log for the full list.</p>")
                % (len(logs) - 200)
            )
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Config Audit] %d change(s) this week") % len(logs),
                "body_html": "".join(rows),
                "recipient_ids": [(6, 0, partners)],
                "author_id": self.env.user.partner_id.id,
            }).send()
        except Exception:
            _logger.exception("ConfigAuditor: mail send failed")

    @api.constrains("extra_sensitive_keys")
    def _check_extra_sensitive_keys(self):
        for rec in self:
            if not rec.extra_sensitive_keys:
                continue
            for line in rec.extra_sensitive_keys.splitlines():
                k = line.strip()
                if k and " " in k:
                    raise ValidationError(_(
                        "Extra sensitive key %r contains whitespace — "
                        "ir.config_parameter keys never contain spaces."
                    ) % k)
