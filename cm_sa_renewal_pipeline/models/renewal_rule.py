import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaRenewalRule(models.Model):
    _name = "cm_sa.renewal.rule"
    _description = "Renewal Pipeline Rule"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Watched Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
        help="Model holding the contract / SO records to watch for expiry.",
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
        string="End-Date Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
        help="The date or datetime field that marks the end of the contract.",
    )
    date_field_name = fields.Char(
        related="date_field_id.name",
        store=True,
        readonly=True,
        string="Date Field Name",
    )
    partner_field_id = fields.Many2one(
        "ir.model.fields",
        string="Customer Field",
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one'),"
               " ('relation', '=', 'res.partner')]",
        help="Many2one to res.partner on the watched model. "
             "Used to populate the opportunity's customer.",
    )
    partner_field_name = fields.Char(
        related="partner_field_id.name", store=True, readonly=True,
        string="Customer Field Name",
    )
    revenue_field_id = fields.Many2one(
        "ir.model.fields",
        string="Revenue Field",
        ondelete="cascade",
        domain="[('model_id', '=', model_id),"
               " ('ttype', 'in', ['float', 'monetary'])]",
        help="Optional numeric field used to prefill the opportunity's "
             "expected revenue (e.g. amount_total).",
    )
    revenue_field_name = fields.Char(
        related="revenue_field_id.name", store=True, readonly=True,
        string="Revenue Field Name",
    )

    lead_days = fields.Integer(
        default=60,
        required=True,
        help="Create the renewal opportunity this many days before the "
             "watched end-date.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Optional extra Odoo domain to restrict to a subset of records.\n"
             "Example: [('state', '=', 'done')]",
    )

    crm_team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        help="Sales team that will own the created opportunity.",
    )
    user_field_id = fields.Many2one(
        "ir.model.fields",
        string="Salesperson Field",
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one'),"
               " ('relation', '=', 'res.users')]",
        help="Optional: inherit salesperson from this field on the source "
             "record. Falls back to the team leader if empty.",
    )
    user_field_name = fields.Char(
        related="user_field_id.name", store=True, readonly=True,
        string="Salesperson Field Name",
    )
    stage_id = fields.Many2one(
        "crm.stage",
        string="Default Stage",
        help="Pipeline stage the new opportunity lands in. Leave empty for "
             "the first stage of the chosen team.",
    )
    quote_template_id = fields.Many2one(
        "sale.order.template",
        string="Renewal Quotation Template",
        help="Optional: if set, stored on the opportunity so the AE can "
             "build the renewal quote from it in one click.",
    )
    tag_ids = fields.Many2many(
        "crm.tag",
        string="Tags",
        help="Optional tags applied to every opportunity created by this rule.",
    )
    name_template = fields.Char(
        string="Opportunity Name Template",
        default="Renew: {customer} — {subject}",
        required=True,
        help="Placeholders:\n"
             "  {customer}  — partner name\n"
             "  {subject}   — source record display name\n"
             "  {end_date}  — watched end-date value",
    )

    last_run = fields.Datetime(readonly=True)
    log_ids = fields.One2many("cm_sa.renewal.log", "rule_id", readonly=True)
    log_count = fields.Integer(compute="_compute_log_count")

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    _name_unique = models.Constraint(
        "unique(name)",
        "A renewal rule with this name already exists.",
    )

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                value = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(_(
                    "Extra Domain is not a valid Python list: %s"
                ) % exc)
            if not isinstance(value, list):
                raise ValidationError(_("Extra Domain must evaluate to a list."))

    @api.constrains("lead_days")
    def _check_lead_days(self):
        for rec in self:
            if rec.lead_days < 0:
                raise ValidationError(_("Lead Days must be >= 0."))

    @api.constrains("name_template")
    def _check_name_template(self):
        for rec in self:
            if not rec.name_template or not rec.name_template.strip():
                raise ValidationError(_("Opportunity Name Template is required."))

    # ------------------------------------------------------------------
    # Scan logic
    # ------------------------------------------------------------------
    def _build_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=self.lead_days)
        domain = [
            (self.date_field_name, "!=", False),
            (self.date_field_name, ">=", fields.Date.to_string(today)),
            (self.date_field_name, "<=", fields.Date.to_string(horizon)),
        ]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _resolve_end_date(self, record):
        self.ensure_one()
        value = record[self.date_field_name]
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return fields.Date.to_date(value)

    def _resolve_partner(self, record):
        self.ensure_one()
        if not self.partner_field_name:
            # Fall back: look for a few common names.
            for candidate in ("partner_id", "partner_invoice_id"):
                if candidate in record._fields:
                    partner = record[candidate]
                    if partner:
                        return partner
            return False
        return record[self.partner_field_name] or False

    def _resolve_user(self, record):
        self.ensure_one()
        if self.user_field_name and self.user_field_name in record._fields:
            user = record[self.user_field_name]
            if user:
                return user
        if self.crm_team_id and self.crm_team_id.user_id:
            return self.crm_team_id.user_id
        return False

    def _resolve_revenue(self, record):
        self.ensure_one()
        if not self.revenue_field_name:
            return 0.0
        value = record[self.revenue_field_name] or 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _resolve_currency(self, record):
        if "currency_id" in record._fields and record.currency_id:
            return record.currency_id
        return self.env.company.currency_id

    def _render_name(self, record, partner, end_date):
        self.ensure_one()
        data = {
            "customer": partner.display_name if partner else _("Customer"),
            "subject": record.display_name or _("Contract #%s") % record.id,
            "end_date": fields.Date.to_string(end_date) if end_date else "",
        }
        try:
            return self.name_template.format(**data)
        except Exception:
            return "Renew: %s" % (record.display_name or record.id)

    def _run_one(self):
        """Scan one rule; create a crm.lead for each unlogged, in-window hit."""
        self.ensure_one()
        if not self.model_name or self.model_name not in self.env:
            _logger.warning(
                "RenewalPipeline: rule %r targets unknown model %r — skipped.",
                self.name, self.model_name,
            )
            return 0

        Model = self.env[self.model_name]
        Log = self.env["cm_sa.renewal.log"]
        Lead = self.env["crm.lead"]
        try:
            records = Model.search(self._build_domain())
        except Exception as exc:
            _logger.exception(
                "RenewalPipeline rule %s: search failed: %s", self.name, exc,
            )
            return 0

        created = 0
        for record in records:
            try:
                end_date = self._resolve_end_date(record)
                if not end_date:
                    continue
                existing = Log.search_count([
                    ("rule_id", "=", self.id),
                    ("res_model", "=", self.model_name),
                    ("res_id", "=", record.id),
                    ("end_date", "=", end_date),
                ])
                if existing:
                    continue

                partner = self._resolve_partner(record)
                user = self._resolve_user(record)
                revenue = self._resolve_revenue(record)
                currency = self._resolve_currency(record)
                display_name = record.display_name or _("Record #%s") % record.id

                lead_vals = {
                    "name": self._render_name(record, partner, end_date),
                    "type": "opportunity",
                    "partner_id": partner.id if partner else False,
                    "team_id": self.crm_team_id.id if self.crm_team_id else False,
                    "stage_id": self.stage_id.id if self.stage_id else False,
                    "user_id": user.id if user else False,
                    "expected_revenue": revenue,
                    "company_currency": currency.id if currency else False,
                    "date_deadline": end_date,
                    "tag_ids": [(6, 0, self.tag_ids.ids)] if self.tag_ids else False,
                    "description": _(
                        "Auto-created by Renewal Pipeline rule '%(rule)s'.\n"
                        "Source: %(model)s / %(name)s\n"
                        "End date: %(end)s"
                    ) % {
                        "rule": self.name,
                        "model": self.model_name,
                        "name": display_name,
                        "end": end_date,
                    },
                }
                try:
                    lead = Lead.create(lead_vals)
                except Exception as exc:
                    _logger.exception(
                        "RenewalPipeline rule %s: lead create failed for %s/%s: %s",
                        self.name, self.model_name, record.id, exc,
                    )
                    continue

                # chatter link on both sides
                if hasattr(record, "message_post"):
                    try:
                        record.message_post(
                            body=_(
                                "Renewal Pipeline [%(rule)s]: created opportunity "
                                "<a href='#' data-oe-model='crm.lead' "
                                "data-oe-id='%(lead_id)s'>%(lead_name)s</a> "
                                "(end date %(end)s)."
                            ) % {
                                "rule": self.name,
                                "lead_id": lead.id,
                                "lead_name": lead.name,
                                "end": end_date,
                            },
                            message_type="comment",
                            subtype_xmlid="mail.mt_note",
                        )
                    except Exception:
                        pass
                try:
                    lead.message_post(
                        body=_(
                            "Source contract: %(model)s / %(name)s (end %(end)s). "
                            "Quote template: %(tpl)s"
                        ) % {
                            "model": self.model_name,
                            "name": display_name,
                            "end": end_date,
                            "tpl": self.quote_template_id.name or _("n/a"),
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
                    "record_name": display_name,
                    "end_date": end_date,
                    "lead_id": lead.id,
                    "partner_id": partner.id if partner else False,
                    "expected_revenue": revenue,
                    "quote_template_id": self.quote_template_id.id or False,
                })
                created += 1
            except Exception:
                _logger.exception(
                    "RenewalPipeline rule %s: record %s/%s failed.",
                    self.name, self.model_name, record.id,
                )
                continue

        self.write({"last_run": fields.Datetime.now()})
        return created

    @api.model
    def _cron_scan(self):
        """Daily cron entry point."""
        for rule in self.search([]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("RenewalPipeline rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            created = rule._run_one()
            rule.message_post(body=_(
                "Renewal Pipeline manual run: %s opportunity(ies) created."
            ) % created) if hasattr(rule, "message_post") else None
        return True

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal Log"),
            "res_model": "cm_sa.renewal.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
