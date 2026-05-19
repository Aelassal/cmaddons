import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Context flag used internally when writing the log row itself — we don't
# want to audit our own audit trail.
CTX_BYPASS = "cm_sa_config_auditor_bypass"


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    # ------------------------------------------------------------------
    # CRUD hooks — capture create/write/unlink on ir.config_parameter
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get(CTX_BYPASS):
            for rec in records:
                self._cm_sa_log_change(
                    change_type="create",
                    key=rec.key,
                    old_value=None,
                    new_value=rec.value,
                )
        return records

    def write(self, vals):
        # Snapshot current values before super() so we capture the diff.
        prior = {
            r.id: {"key": r.key, "value": r.value} for r in self
        } if not self.env.context.get(CTX_BYPASS) else None
        res = super().write(vals)
        if prior is not None:
            for rec in self:
                before = prior.get(rec.id, {})
                self._cm_sa_log_change(
                    change_type="write",
                    key=rec.key,
                    old_value=before.get("value"),
                    new_value=rec.value,
                    old_key=before.get("key"),
                )
        return res

    def unlink(self):
        if not self.env.context.get(CTX_BYPASS):
            for rec in self:
                self._cm_sa_log_change(
                    change_type="unlink",
                    key=rec.key,
                    old_value=rec.value,
                    new_value=None,
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    def _cm_sa_log_change(self, change_type, key, old_value, new_value, old_key=None):
        Settings = self.env["cm_sa.config_auditor.settings"].sudo()
        Log = self.env["cm_sa.config.change.log"].sudo()
        try:
            cfg = Settings.get_singleton()
        except Exception:
            _logger.exception("ConfigAuditor: could not load settings; skip log.")
            return
        if not cfg.active:
            return
        sensitive_keys = cfg._sensitive_key_set()
        try:
            is_sensitive = (key in sensitive_keys) or (
                old_key and old_key in sensitive_keys
            )
        except Exception:
            is_sensitive = False
        # If the key itself changed on a write, record both under the new key
        # but flag the old-key diff in the old_value text.
        old_text = old_value
        if old_key and old_key != key:
            old_text = _("[key renamed from '%s'] %s") % (old_key, old_value or "")

        try:
            Log.with_context(**{CTX_BYPASS: True}).create({
                "key": key or (old_key or ""),
                "change_type": change_type,
                "old_value": (old_text or "")[:4000] if old_text else False,
                "new_value": (new_value or "")[:4000] if new_value else False,
                "user_id": self.env.user.id,
                "is_sensitive": is_sensitive,
            })
        except Exception:
            _logger.exception(
                "ConfigAuditor: failed to write log row for key=%s", key,
            )
            return

        if is_sensitive and cfg.alert_on_sensitive and cfg.notify_group_id:
            try:
                self._cm_sa_send_alert(cfg, change_type, key, old_value, new_value)
            except Exception:
                _logger.exception(
                    "ConfigAuditor: failed to send alert for key=%s", key,
                )

    def _cm_sa_send_alert(self, cfg, change_type, key, old_value, new_value):
        partners = [u.partner_id.id for u in cfg.notify_group_id.users if u.partner_id]
        if not partners:
            return
        body = _(
            "<p><b>[Config Audit]</b> Sensitive key <code>%(key)s</code> "
            "changed by <b>%(user)s</b> (%(type)s).</p>"
            "<p><b>Old:</b> <code>%(old)s</code><br/>"
            "<b>New:</b> <code>%(new)s</code></p>"
        ) % {
            "key": key,
            "user": self.env.user.display_name,
            "type": change_type,
            "old": (old_value or "")[:300] if old_value else "(none)",
            "new": (new_value or "")[:300] if new_value else "(none)",
        }
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Config Audit] Sensitive change: %s") % key,
                "body_html": body,
                "recipient_ids": [(6, 0, partners)],
                "author_id": self.env.user.partner_id.id,
            }).send()
        except Exception:
            _logger.exception("ConfigAuditor: mail send failed")
