import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaExpiryRule(models.Model):
    _name = "cm_sa.expiry.rule"
    _description = "Expiry Watcher Rule"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

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
        index=True,
    )
    date_field_id = fields.Many2one(
        "ir.model.fields",
        string="Date Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
    )
    date_field_name = fields.Char(
        related="date_field_id.name",
        store=True,
        readonly=True,
    )
    name_expression = fields.Char(
        default="record.display_name",
        required=True,
        help="Python expression evaluated against 'record' to build the display "
             "name in notifications. Default: record.display_name",
    )
    lead_days = fields.Integer(
        default=30,
        required=True,
        help="How many days before expiry to start alerting.",
    )
    notify_user_ids = fields.Many2many(
        "res.users",
        "cm_sa_expiry_rule_user_rel",
        "rule_id",
        "user_id",
        string="Notify Users",
    )
    email_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain="[('model_id', '=', model_id)]",
        help="Optional. If set, this template is rendered per record and emailed "
             "to the notified users.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Extra Odoo domain filter, appended to the date window. "
             "Example: [('state', '=', 'active')]",
    )
    last_run = fields.Datetime(readonly=True)

    log_ids = fields.One2many("cm_sa.expiry.log", "rule_id", readonly=True)
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
                raise ValidationError(_(
                    "Extra domain is not a valid Python list: %s"
                ) % exc)
            if not isinstance(domain, list):
                raise ValidationError(_("Extra domain must evaluate to a list."))

    @api.constrains("lead_days")
    def _check_lead_days(self):
        for rec in self:
            if rec.lead_days < 0:
                raise ValidationError(_("Lead days must be >= 0."))

    # ------------------------------------------------------------------
    # Scan logic
    # ------------------------------------------------------------------
    def _build_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=self.lead_days)
        field_name = self.date_field_name
        domain = [
            (field_name, "!=", False),
            (field_name, ">=", fields.Date.to_string(today)),
            (field_name, "<=", fields.Date.to_string(horizon)),
        ]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _resolve_expiry_date(self, record):
        self.ensure_one()
        value = record[self.date_field_name]
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return fields.Date.to_date(value)

    def _render_display_name(self, record):
        self.ensure_one()
        try:
            return safe_eval(
                self.name_expression or "record.display_name",
                {"__builtins__": {}, "record": record},
            )
        except Exception:
            return record.display_name or _("Record #%s") % record.id

    def _run_one(self):
        """Scan one rule; create log rows + notifications for each hit."""
        self.ensure_one()
        if not self.model_name or self.model_name not in self.env:
            _logger.warning(
                "ExpiryWatcher: rule %r targets unknown model %r — skipped.",
                self.name, self.model_name,
            )
            return

        Model = self.env[self.model_name]
        Log = self.env["cm_sa.expiry.log"]
        today = fields.Date.context_today(self)
        try:
            records = Model.search(self._build_domain())
        except Exception as exc:
            _logger.exception(
                "ExpiryWatcher rule %s: search failed: %s", self.name, exc,
            )
            return

        for record in records:
            try:
                expiry = self._resolve_expiry_date(record)
                if not expiry:
                    continue
                existing = Log.search_count([
                    ("rule_id", "=", self.id),
                    ("res_model", "=", self.model_name),
                    ("res_id", "=", record.id),
                    ("expiry_date", "=", expiry),
                ])
                if existing:
                    continue
                days_remaining = (expiry - today).days
                display_name = self._render_display_name(record)

                email_sent = False
                if self.email_template_id and self.notify_user_ids:
                    try:
                        self.email_template_id.with_context(
                            expiry_days_remaining=days_remaining,
                            expiry_rule_name=self.name,
                        ).send_mail(
                            record.id,
                            force_send=False,
                            email_values={
                                "recipient_ids": [
                                    (4, u.partner_id.id) for u in self.notify_user_ids
                                    if u.partner_id
                                ],
                            },
                        )
                        email_sent = True
                    except Exception as exc:
                        _logger.warning(
                            "ExpiryWatcher: email render failed for %s/%s: %s",
                            self.model_name, record.id, exc,
                        )

                # chatter post on the target record when it supports it
                if hasattr(Model, "message_post"):
                    try:
                        record.message_post(
                            body=_(
                                "Expiry watcher [%(rule)s]: "
                                "<b>%(name)s</b> expires on %(date)s "
                                "(%(days)s day(s) remaining)."
                            ) % {
                                "rule": self.name,
                                "name": display_name,
                                "date": expiry,
                                "days": days_remaining,
                            },
                            message_type="comment",
                            subtype_xmlid="mail.mt_note",
                        )
                    except Exception:
                        pass

                Log.create({
                    "rule_id": self.id,
                    "res_model": self.model_name,
                    "res_id": record.id,
                    "record_name": display_name or False,
                    "expiry_date": expiry,
                    "days_remaining": days_remaining,
                    "notified_user_ids": [(6, 0, self.notify_user_ids.ids)],
                    "email_sent": email_sent,
                })
            except Exception:
                _logger.exception(
                    "ExpiryWatcher rule %s: record %s/%s failed.",
                    self.name, self.model_name, record.id,
                )
                continue

        self.write({"last_run": fields.Datetime.now()})

    @api.model
    def _cron_scan(self):
        """Daily cron entry point."""
        for rule in self.search([]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("ExpiryWatcher rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            rule._run_one()
        return True

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Expiry Log"),
            "res_model": "cm_sa.expiry.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
