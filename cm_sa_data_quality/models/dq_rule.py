import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

RULE_TYPES = [
    ("field_required", "Required Field"),
    ("regex_format", "Regex Format"),
    ("value_in_list", "Value in List"),
    ("stale_value_days", "Stale Value"),
    ("orphan_reference", "Orphan Reference"),
]


class CmSaDqRule(models.Model):
    _name = "cm_sa.dq.rule"
    _description = "Data Quality Rule"
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
        index=True,
    )
    rule_type = fields.Selection(
        RULE_TYPES,
        required=True,
        default="field_required",
    )
    severity = fields.Selection(
        [("info", "Info"), ("warn", "Warn"), ("fail", "Fail")],
        required=True,
        default="warn",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        domain="[('model_id', '=', model_id)]",
        ondelete="cascade",
        help="Field to evaluate (required for most rule types).",
    )
    regex_pattern = fields.Char(
        string="Regex Pattern",
        help="Used only for Regex Format rules. Full-match is required.",
    )
    value_list = fields.Char(
        string="Allowed Values (comma-separated)",
        help="Used only for Value-in-List rules.",
    )
    stale_days = fields.Integer(
        string="Stale After (days)",
        default=180,
        help="Used only for Stale Value rules. Records whose last write "
             "of the field is older than N days are flagged.",
    )
    orphan_field_id = fields.Many2one(
        "ir.model.fields",
        string="Orphan FK Field",
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one')]",
        ondelete="cascade",
        help="Used only for Orphan Reference rules. Picks the many2one "
             "field whose target may be missing.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Additional filter domain to narrow the records the rule "
             "applies to. Example: [('active', '=', True)].",
    )
    limit_records = fields.Integer(
        default=0,
        help="If > 0, only scan up to N records per run (safety valve for "
             "huge tables). 0 = unlimited.",
    )

    finding_ids = fields.One2many("cm_sa.dq.finding", "rule_id", readonly=True)
    finding_count = fields.Integer(compute="_compute_finding_count")

    @api.depends("finding_ids", "finding_ids.resolved")
    def _compute_finding_count(self):
        for rec in self:
            rec.finding_count = len(
                rec.finding_ids.filtered(lambda f: not f.resolved)
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                val = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(
                    _("Extra domain is not a valid expression: %s") % exc
                )
            if not isinstance(val, list):
                raise ValidationError(_("Extra domain must evaluate to a list."))

    @api.constrains("rule_type", "field_id", "regex_pattern", "value_list",
                    "stale_days", "orphan_field_id")
    def _check_type_specific(self):
        for rec in self:
            if rec.rule_type in ("field_required", "regex_format",
                                  "value_in_list", "stale_value_days"):
                if not rec.field_id:
                    raise ValidationError(_(
                        "Rule type %s requires a Field."
                    ) % dict(RULE_TYPES).get(rec.rule_type))
            if rec.rule_type == "regex_format":
                if not rec.regex_pattern:
                    raise ValidationError(_("Regex rules require a pattern."))
                try:
                    re.compile(rec.regex_pattern)
                except re.error as exc:
                    raise ValidationError(_("Invalid regex: %s") % exc)
            if rec.rule_type == "value_in_list" and not rec.value_list:
                raise ValidationError(_(
                    "Value-in-List rules require an allowed-values list."
                ))
            if rec.rule_type == "stale_value_days" and rec.stale_days <= 0:
                raise ValidationError(_("Stale days must be > 0."))
            if rec.rule_type == "orphan_reference" and not rec.orphan_field_id:
                raise ValidationError(_(
                    "Orphan Reference rules require the Orphan FK Field."
                ))

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _records_for_scan(self):
        self.ensure_one()
        if not self.model_name or self.model_name not in self.env:
            return self.env["ir.model"].browse()
        try:
            domain = safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        except Exception:
            domain = []
        Model = self.env[self.model_name].sudo()
        if self.limit_records and self.limit_records > 0:
            return Model.search(domain, limit=self.limit_records)
        return Model.search(domain)

    def _split_value_list(self):
        self.ensure_one()
        if not self.value_list:
            return []
        return [v.strip() for v in self.value_list.split(",") if v.strip()]

    def _evaluate(self, record):
        """Return (failed, detail) tuple. detail is a short string or False."""
        self.ensure_one()
        rt = self.rule_type
        if rt == "field_required":
            fname = self.field_id.name
            if fname not in record._fields:
                return (False, False)
            value = record[fname]
            if not value:
                return (True, _("Empty value"))
            return (False, False)
        if rt == "regex_format":
            fname = self.field_id.name
            if fname not in record._fields:
                return (False, False)
            value = record[fname]
            if value in (False, None, ""):
                # treat empty as not applicable unless severity == fail
                return (False, False)
            text = str(value)
            try:
                if not re.fullmatch(self.regex_pattern, text):
                    return (True, _("Value %r does not match pattern") % text[:80])
            except Exception:
                return (False, False)
            return (False, False)
        if rt == "value_in_list":
            fname = self.field_id.name
            if fname not in record._fields:
                return (False, False)
            value = record[fname]
            if value in (False, None, ""):
                return (False, False)
            allowed = self._split_value_list()
            if str(value) not in allowed:
                return (True, _("Value %r not in allow-list") % str(value)[:80])
            return (False, False)
        if rt == "stale_value_days":
            fname = self.field_id.name
            if fname not in record._fields:
                return (False, False)
            # Use the record's write_date as a coarse signal: if the
            # record has not been touched in N days at all, we call it
            # stale for this field. Field-level tracking would require
            # inspecting mail.tracking.value; we keep it simple.
            wd = record.write_date
            if not wd:
                return (False, False)
            cutoff = fields.Datetime.now() - timedelta(days=self.stale_days)
            if wd < cutoff:
                return (True, _("No writes since %s") % fields.Date.to_string(wd))
            return (False, False)
        if rt == "orphan_reference":
            fname = self.orphan_field_id.name
            if fname not in record._fields:
                return (False, False)
            target = record[fname]
            # Many2one returns an empty recordset if the FK value points
            # to a gone record, but we also check raw value where available.
            try:
                stored_val = record.read([fname])[0].get(fname)
            except Exception:
                stored_val = None
            if stored_val and not target:
                return (True, _("Dangling reference: %s") % stored_val)
            # If set and the target is soft-absent (e.g. archived):
            if target and not target.exists():
                return (True, _("Target no longer exists"))
            return (False, False)
        return (False, False)

    def _run_one(self, scan):
        """Scan one rule, upsert findings, return count tuples."""
        self.ensure_one()
        Finding = self.env["cm_sa.dq.finding"].sudo()
        new_count = 0
        updated_count = 0
        scanned = 0
        try:
            records = self._records_for_scan()
        except Exception:
            _logger.exception("dq: rule %s failed to load records", self.name)
            return (0, 0, 0)
        now = fields.Datetime.now()
        for record in records:
            scanned += 1
            try:
                failed, detail = self._evaluate(record)
            except Exception:
                _logger.exception(
                    "dq: evaluate failed for %s:%s on rule %s",
                    self.model_name, record.id, self.name,
                )
                continue
            existing = Finding.search([
                ("rule_id", "=", self.id),
                ("res_model", "=", self.model_name),
                ("res_id", "=", record.id),
            ], limit=1)
            if failed:
                if existing:
                    vals = {
                        "last_seen": now,
                        "severity": self.severity,
                        "resolved": False,
                        "resolved_at": False,
                        "detail": detail or False,
                    }
                    if not existing.record_name:
                        vals["record_name"] = record.display_name or False
                    existing.write(vals)
                    updated_count += 1
                else:
                    Finding.create({
                        "rule_id": self.id,
                        "res_model": self.model_name,
                        "res_id": record.id,
                        "record_name": record.display_name or False,
                        "first_seen": now,
                        "last_seen": now,
                        "severity": self.severity,
                        "detail": detail or False,
                    })
                    new_count += 1
                    # Chatter-post on NEW findings only.
                    if hasattr(record, "message_post"):
                        try:
                            record.message_post(
                                body=_(
                                    "Data quality: rule <b>%(rule)s</b> "
                                    "flagged this record. %(detail)s"
                                ) % {
                                    "rule": self.name,
                                    "detail": detail or "",
                                },
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                            )
                        except Exception:
                            pass
            else:
                if existing and not existing.resolved:
                    existing.write({
                        "resolved": True,
                        "resolved_at": now,
                    })
        return (new_count, updated_count, scanned)

    # ------------------------------------------------------------------
    # Cron entry points
    # ------------------------------------------------------------------
    @api.model
    def _cron_scan(self):
        Scan = self.env["cm_sa.dq.scan"].sudo()
        scan = Scan.create({})
        started = fields.Datetime.now()
        info = warn = fail = 0
        scanned_total = 0
        rules = self.search([("active", "=", True)])
        for rule in rules:
            new, updated, n = rule._run_one(scan)
            scanned_total += n
            if rule.severity == "info":
                info += new
            elif rule.severity == "warn":
                warn += new
            elif rule.severity == "fail":
                fail += new
        ended = fields.Datetime.now()
        duration = (ended - started).total_seconds()
        scan.write({
            "completed_at": ended,
            "rules_run": len(rules),
            "records_scanned": scanned_total,
            "findings_info": info,
            "findings_warn": warn,
            "findings_fail": fail,
            "duration_seconds": duration,
        })
        _logger.info(
            "dq: scan %s completed in %.1fs; rules=%d scanned=%d "
            "new(info=%d, warn=%d, fail=%d).",
            scan.id, duration, len(rules), scanned_total, info, warn, fail,
        )
        return scan

    def action_run_now(self):
        """Button: run this rule immediately."""
        Scan = self.env["cm_sa.dq.scan"].sudo()
        scan = Scan.create({})
        started = fields.Datetime.now()
        info = warn = fail = 0
        scanned_total = 0
        for rule in self:
            new, updated, n = rule._run_one(scan)
            scanned_total += n
            if rule.severity == "info":
                info += new
            elif rule.severity == "warn":
                warn += new
            elif rule.severity == "fail":
                fail += new
        ended = fields.Datetime.now()
        scan.write({
            "completed_at": ended,
            "rules_run": len(self),
            "records_scanned": scanned_total,
            "findings_info": info,
            "findings_warn": warn,
            "findings_fail": fail,
            "duration_seconds": (ended - started).total_seconds(),
            "notes": "Manual run",
        })
        return True

    def action_view_findings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Findings"),
            "res_model": "cm_sa.dq.finding",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }

    # ------------------------------------------------------------------
    # Weekly email summary
    # ------------------------------------------------------------------
    @api.model
    def _cron_weekly_summary(self):
        """Send the admin a top-offenders summary email."""
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if not admin or not admin.partner_id:
            return
        rules = self.search([("active", "=", True)])
        ranked = sorted(
            rules,
            key=lambda r: len(r.finding_ids.filtered(lambda f: not f.resolved)),
            reverse=True,
        )[:10]
        if not ranked:
            return
        rows = []
        for r in ranked:
            open_count = len(r.finding_ids.filtered(lambda f: not f.resolved))
            rows.append(
                "<tr><td>%s</td><td>%s</td>"
                "<td align='right'>%s</td></tr>" % (
                    (r.name or "").replace("<", "&lt;"),
                    (r.model_name or "").replace("<", "&lt;"),
                    open_count,
                )
            )
        body_html = (
            "<div style='font-family:Arial,sans-serif;'>"
            "<h3>Data Quality &mdash; weekly top offending rules</h3>"
            "<p>Top active rules by unresolved finding count:</p>"
            "<table border='1' cellpadding='6' cellspacing='0' "
            "style='border-collapse:collapse;'>"
            "<thead><tr style='background:#f5f5f5;'>"
            "<th align='left'>Rule</th>"
            "<th align='left'>Model</th>"
            "<th align='right'>Unresolved</th>"
            "</tr></thead>"
            "<tbody>%s</tbody>"
            "</table>"
            "<p style='color:#888;font-size:11px;'>"
            "Open <b>Data Quality &rarr; Findings</b> in your Odoo database to triage."
            "</p>"
            "</div>"
        ) % "".join(rows)
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("Data Quality — weekly top rules"),
                "body_html": body_html,
                "email_from": (
                    admin.email_formatted
                    or (admin.company_id.email if admin.company_id else False)
                    or "noreply@example.com"
                ),
                "recipient_ids": [(4, admin.partner_id.id)],
            }).send(raise_exception=False)
        except Exception:
            _logger.exception("dq: weekly summary email failed.")
