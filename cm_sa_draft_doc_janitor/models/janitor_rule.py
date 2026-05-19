import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaJanitorRule(models.Model):
    _name = "cm_sa.janitor.rule"
    _description = "Draft Document Janitor Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        string="Model Name",
    )

    state_field = fields.Char(
        default="state",
        help="Name of the state field to check (e.g. 'state').",
    )
    draft_state_value = fields.Char(
        default="draft",
        help="Value of the state field that means 'draft'.",
    )
    age_days = fields.Integer(
        required=True,
        default=30,
        help="A record is considered stale after this many days.",
    )
    date_field = fields.Char(
        default="write_date",
        help="Date column to age against. Defaults to write_date.",
    )
    action = fields.Selection(
        [
            ("notify_owner", "Notify owner"),
            ("auto_cancel", "Auto-cancel"),
            ("auto_archive", "Auto-archive"),
        ],
        required=True,
        default="notify_owner",
    )
    cancel_method = fields.Char(
        default="button_cancel",
        help="Method to call on the record when action='auto_cancel' (e.g. button_cancel, action_cancel).",
    )
    notify_template_id = fields.Many2one(
        "mail.template",
        string="Notification Template",
        help="Mail template used when action='notify_owner'.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Extra Odoo domain appended to the draft + age filter. Example: [('amount_total', '>', 0)]",
    )

    log_ids = fields.One2many(
        "cm_sa.janitor.log",
        "rule_id",
        readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                domain = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(_("Extra domain is not a valid Python list: %s") % exc)
            if not isinstance(domain, list):
                raise ValidationError(_("Extra domain must evaluate to a list."))

    @api.constrains("action", "notify_template_id")
    def _check_notify_template(self):
        for rec in self:
            if rec.action == "notify_owner" and not rec.notify_template_id:
                raise ValidationError(_(
                    "A notification mail template is required when the action is 'Notify owner'."
                ))

    def _build_domain(self):
        self.ensure_one()
        cutoff = fields.Datetime.now() - timedelta(days=self.age_days)
        domain = [
            (self.state_field, "=", self.draft_state_value),
            (self.date_field, "<", fields.Datetime.to_string(cutoff)),
        ]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _resolve_owner(self, record):
        """Pick the user to notify: user_id if it exists and is set, else create_uid."""
        self.ensure_one()
        owner = False
        if "user_id" in record._fields:
            owner = record.user_id
        if not owner and "create_uid" in record._fields:
            owner = record.create_uid
        return owner or False

    def _post_chatter(self, record, action_label):
        """Post to chatter only if the model inherits mail.thread."""
        self.ensure_one()
        Model = self.env[self.model_name]
        if not hasattr(Model, "message_post"):
            return
        try:
            record.message_post(
                body=_("Janitor action: %(action)s (rule: %(rule)s)") % {
                    "action": action_label,
                    "rule": self.name,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception as exc:
            _logger.warning("Janitor: chatter post failed on %s,%s: %s", self.model_name, record.id, exc)

    def _log(self, record, action_taken, error_message=False):
        self.ensure_one()
        record_ref = False
        record_name = False
        if record and record.id:
            record_ref = "%s,%s" % (self.model_name, record.id)
            try:
                record_name = record.display_name
            except Exception:
                record_name = "%s,%s" % (self.model_name, record.id)
        return self.env["cm_sa.janitor.log"].create({
            "rule_id": self.id,
            "record_ref": record_ref,
            "model_name": self.model_name,
            "record_name": record_name,
            "action_taken": action_taken,
            "error_message": error_message or False,
        })

    def _apply_notify(self, record):
        self.ensure_one()
        owner = self._resolve_owner(record)
        if not owner:
            self._log(record, "error", _("No owner (user_id / create_uid) on record."))
            return
        try:
            self.notify_template_id.send_mail(record.id, force_send=False, email_values={
                "email_to": owner.email or False,
                "recipient_ids": [(4, owner.partner_id.id)] if owner.partner_id else False,
            })
        except Exception as exc:
            self._log(record, "error", _("Notification send failed: %s") % exc)
            return
        self._post_chatter(record, _("Notify owner"))
        self._log(record, "notify_owner")

    def _apply_cancel(self, record):
        self.ensure_one()
        method = getattr(record, self.cancel_method, None)
        if not callable(method):
            self._log(record, "error", _(
                "Cancel method '%s' not found on %s."
            ) % (self.cancel_method, self.model_name))
            return
        try:
            method()
        except (UserError, AccessError) as exc:
            self._log(record, "error", _("Auto-cancel failed: %s") % exc)
            return
        except Exception as exc:
            self._log(record, "error", _("Auto-cancel raised: %s") % exc)
            return
        self._post_chatter(record, _("Auto-cancel"))
        self._log(record, "auto_cancel")

    def _apply_archive(self, record):
        self.ensure_one()
        if "active" not in record._fields:
            self._log(record, "error", _("Model %s has no 'active' field.") % self.model_name)
            return
        try:
            record.write({"active": False})
        except (UserError, AccessError) as exc:
            self._log(record, "error", _("Auto-archive failed: %s") % exc)
            return
        self._post_chatter(record, _("Auto-archive"))
        self._log(record, "auto_archive")

    def _run_one(self):
        """Run a single rule: scan, act, log."""
        self.ensure_one()
        if not self.model_name or self.model_name not in self.env:
            self.env["cm_sa.janitor.log"].create({
                "rule_id": self.id,
                "model_name": self.model_name,
                "record_name": self.name,
                "action_taken": "error",
                "error_message": _("Model '%s' is not installed.") % self.model_name,
            })
            return
        Model = self.env[self.model_name]
        try:
            records = Model.search(self._build_domain())
        except Exception as exc:
            _logger.warning("Janitor rule %s: search failed: %s", self.name, exc)
            return

        for record in records:
            try:
                if self.action == "notify_owner":
                    self._apply_notify(record)
                elif self.action == "auto_cancel":
                    self._apply_cancel(record)
                elif self.action == "auto_archive":
                    self._apply_archive(record)
            except Exception:
                _logger.exception(
                    "Janitor rule %s: record %s,%s failed.",
                    self.name, self.model_name, record.id,
                )
                continue

    @api.model
    def _run_all(self):
        """Cron entry point: run every active rule in sequence order."""
        Log = self.env["cm_sa.janitor.log"]
        for rule in self.search([]):
            if rule.model_name not in self.env:
                Log.create({
                    "rule_id": rule.id,
                    "model_name": rule.model_name,
                    "record_name": rule.name,
                    "action_taken": "error",
                    "error_message": _("Model '%s' is not installed; skipping rule.") % rule.model_name,
                })
                continue
            try:
                rule._run_one()
            except Exception as exc:
                _logger.exception("Janitor rule %s failed: %s", rule.name, exc)

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Janitor Log"),
            "res_model": "cm_sa.janitor.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }

    def action_run_now(self):
        for rule in self:
            rule._run_one()
        return True
