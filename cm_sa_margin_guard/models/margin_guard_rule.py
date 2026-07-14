import ast
import logging
import math
import re
from collections import defaultdict

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

_MARGIN_MARKER = "_cm_sa_margin_guard_wrapper"
_MARGIN_ORIGINAL = "_cm_sa_margin_guard_original"
_MARGIN_WRAPPER_VERSION = "_cm_sa_margin_guard_wrapper_version"
_CURRENT_WRAPPER_VERSION = 2

CTX_REASON = "cm_sa_margin_override_reason"
CTX_BYPASS = "cm_sa_margin_guard_bypass"
CTX_AUDIT_CREATE = "cm_sa_margin_guard_audit_create"
_INTERNAL_BYPASS_TOKEN = object()

_ALLOWED_ERROR_KEYS = {"model", "actual", "threshold"}
_ERROR_TOKEN_RE = re.compile(
    r"%(?:%|\((?P<key>[A-Za-z_][A-Za-z0-9_]*)\)"
    r"[#0\- +]?(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrs])"
)
_METHOD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_SO_FORMULA = (
    "(record.amount_untaxed - sum(line.product_id.standard_price * line.product_uom_qty "
    "for line in record.order_line)) / record.amount_untaxed * 100 "
    "if record.amount_untaxed else 100"
)


class CmSaMarginGuardRule(models.Model):
    _name = "cm_sa.margin.guard.rule"
    _description = "Sale-Order Margin Guard Rule"
    _order = "model_name, method_name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
        tracking=True,
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        index=True,
        string="Technical Model Name",
    )
    method_name = fields.Char(
        string="Method to Guard",
        required=True,
        default="action_confirm",
        help="Name of the method to wrap. For sale.order this is usually "
        "action_confirm. Custom buttons work too.",
        tracking=True,
    )
    margin_formula = fields.Text(
        required=True,
        default=DEFAULT_SO_FORMULA,
        help="Python expression evaluated against 'record'. Must return "
        "a number - the margin percentage. Default formula computes "
        "gross margin % from product cost on sale.order lines.",
        tracking=True,
    )
    threshold_pct = fields.Float(
        string="Minimum Margin %",
        required=True,
        default=10.0,
        help="Records below this percentage trigger the guard.",
        tracking=True,
    )
    domain = fields.Char(
        default="[]",
        help="Optional Odoo domain to scope the rule to a subset of records.",
        tracking=True,
    )
    override_group_id = fields.Many2one(
        "res.groups",
        string="Override Group",
        help="Members of this group may confirm below-threshold records "
        "after supplying a reason. Leave empty to block all below-threshold "
        "confirmations unconditionally.",
        tracking=True,
    )
    require_reason_on_override = fields.Boolean(
        default=True,
        help="When enabled, a wizard asks the override-group user for a reason "
        "before the confirmation runs.",
        tracking=True,
    )
    min_reason_length = fields.Integer(
        default=10,
        help="Minimum characters required in the override reason.",
        tracking=True,
    )
    error_message = fields.Char(
        default="This %(model)s is below the required margin "
        "(%(actual).1f%% < %(threshold).1f%%). Override blocked.",
        required=True,
        help="Allowed placeholders: %(model)s, %(actual).1f, %(threshold).1f. "
        "Use %% for a literal percent sign.",
        tracking=True,
    )

    log_ids = fields.One2many(
        "cm_sa.margin.override.log", "rule_id", readonly=True
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A margin-guard rule with this name already exists.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("domain")
    def _check_domain(self):
        for rec in self:
            try:
                value = safe_eval(rec.domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(
                    _("Domain is not a valid Python expression: %s") % exc
                ) from exc
            if not isinstance(value, list):
                raise ValidationError(_("Domain must evaluate to a list."))
            if rec.model_id and rec.model_id.model in self.env.registry:
                try:
                    self.env[rec.model_id.model].sudo().search(value, limit=1)
                except Exception as exc:
                    raise ValidationError(
                        _("Domain is not valid for model %(model)s: %(detail)s")
                        % {
                            "model": rec.model_id.model,
                            "detail": str(exc),
                        }
                    ) from exc

    @api.constrains("margin_formula")
    def _check_formula(self):
        for rec in self:
            expression = (rec.margin_formula or "").strip()
            if not expression:
                raise ValidationError(_("Margin Formula is required."))
            try:
                ast.parse(expression, mode="eval")
            except SyntaxError as exc:
                details = exc.msg
                if exc.lineno:
                    details = _("%(message)s at line %(line)s") % {
                        "message": details,
                        "line": exc.lineno,
                    }
                raise ValidationError(
                    _("Margin Formula has invalid Python syntax: %s") % details
                ) from exc

    @api.constrains("threshold_pct")
    def _check_threshold(self):
        for rec in self:
            if rec.threshold_pct < -1000 or rec.threshold_pct > 1000:
                raise ValidationError(
                    _("Threshold must be between -1000 and 1000.")
                )

    @api.constrains("min_reason_length")
    def _check_min_reason_length(self):
        for rec in self:
            if rec.min_reason_length < 0:
                raise ValidationError(
                    _("Minimum reason length cannot be negative.")
                )

    @api.constrains("method_name", "model_id", "active")
    def _check_target_method(self):
        for rec in self:
            method_name = (rec.method_name or "").strip()
            if not method_name:
                raise ValidationError(_("Method to Guard is required."))
            if not _METHOD_NAME_RE.fullmatch(method_name):
                raise ValidationError(
                    _("Method to Guard must be a valid Python method name.")
                )
            if not rec.active or not rec.model_id:
                continue
            model_name = rec.model_id.model
            if not model_name or model_name not in self.env.registry:
                raise ValidationError(
                    _("The target model '%s' is not available in the registry.")
                    % (model_name or "")
                )
            method = getattr(type(self.env[model_name]), method_name, None)
            if not callable(method):
                raise ValidationError(
                    _("Model %(model)s has no callable method %(method)s.")
                    % {"model": model_name, "method": method_name}
                )

    @api.constrains("error_message")
    def _check_error_message(self):
        for rec in self:
            self._validate_error_message_template(rec.error_message)

    @api.model
    def _validate_error_message_template(self, message):
        if not message:
            raise ValidationError(_("Error Message is required."))

        keys = set()
        cursor = 0
        for match in _ERROR_TOKEN_RE.finditer(message):
            if "%" in message[cursor:match.start()]:
                raise ValidationError(
                    _(
                        "Invalid Error Message placeholder. Use only "
                        "%(model)s, %(actual).1f, %(threshold).1f and %% for "
                        "a literal percent sign."
                    )
                )
            key = match.group("key")
            if key:
                keys.add(key)
            cursor = match.end()
        if "%" in message[cursor:]:
            raise ValidationError(
                _(
                    "Invalid Error Message placeholder. Use only "
                    "%(model)s, %(actual).1f, %(threshold).1f and %% for "
                    "a literal percent sign."
                )
            )

        unknown = keys - _ALLOWED_ERROR_KEYS
        if unknown:
            raise ValidationError(
                _("Unsupported Error Message placeholder(s): %s")
                % ", ".join(sorted(unknown))
            )

        try:
            message % {
                "model": "SO0001",
                "actual": 5.25,
                "threshold": 10.0,
            }
        except Exception as exc:
            raise ValidationError(
                _("Error Message cannot be formatted: %s") % exc
            ) from exc

    # ------------------------------------------------------------------
    # Dynamic wrappers
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if self._table_exists():
            self._install_active_wrappers()

    def _table_exists(self):
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (self._table,),
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    @api.model
    def _install_active_wrappers(self, pairs=None):
        if not self._table_exists():
            return

        if pairs is None:
            rules = self.sudo().search([("active", "=", True)])
            pairs = {
                (rule.model_name, (rule.method_name or "").strip())
                for rule in rules
                if rule.model_name and rule.method_name
            }
        else:
            pairs = {
                (model_name, (method_name or "").strip())
                for model_name, method_name in pairs
                if model_name and method_name
            }

        installed = 0
        for model_name, method_name in pairs:
            if model_name not in self.env.registry:
                _logger.error(
                    "MarginGuard: target model %s is not available.", model_name
                )
                continue

            cls = type(self.env[model_name])
            current = getattr(cls, method_name, None)
            if current is None or not callable(current):
                _logger.error(
                    "MarginGuard: %s.%s is not callable.",
                    model_name,
                    method_name,
                )
                continue

            if (
                getattr(current, _MARGIN_MARKER, False)
                and getattr(current, _MARGIN_WRAPPER_VERSION, 0)
                == _CURRENT_WRAPPER_VERSION
            ):
                continue

            original = (
                getattr(current, _MARGIN_ORIGINAL, current)
                if getattr(current, _MARGIN_MARKER, False)
                else current
            )
            wrapper = self._build_wrapper(model_name, method_name, original)
            setattr(wrapper, _MARGIN_MARKER, True)
            setattr(wrapper, _MARGIN_ORIGINAL, original)
            setattr(
                wrapper, _MARGIN_WRAPPER_VERSION, _CURRENT_WRAPPER_VERSION
            )
            wrapper.__name__ = method_name
            wrapper.__qualname__ = f"{cls.__name__}.{method_name}"
            setattr(cls, method_name, wrapper)
            installed += 1

        if installed:
            _logger.info(
                "MarginGuard: installed or refreshed %d dynamic wrapper(s).",
                installed,
            )

    @staticmethod
    def _build_wrapper(model_name, method_name, original):
        def guarded(records, *args, **kwargs):
            if records.env.context.get(CTX_BYPASS) is _INTERNAL_BYPASS_TOKEN:
                return original(records, *args, **kwargs)
            Rule = records.env["cm_sa.margin.guard.rule"].sudo()
            return Rule._execute_guarded_call(
                records,
                model_name,
                method_name,
                original,
                args,
                kwargs,
            )

        return guarded

    @api.model
    def _execute_guarded_call(
        self, records, model_name, method_name, original, args, kwargs
    ):
        rules = self.search(
            [
                ("active", "=", True),
                ("model_name", "=", model_name),
                ("method_name", "=", method_name),
            ],
            order="id",
        )
        if not rules or not records:
            return self._call_original(original, records, args, kwargs)

        violations = self._evaluate_violations(records, rules)
        if not violations:
            return self._call_original(original, records, args, kwargs)

        reason = (records.env.context.get(CTX_REASON) or "").strip()
        user_group_ids = set(records.env.user.all_group_ids.ids)

        safe_records = records.filtered(lambda rec: not violations.get(rec.id))
        blocked_records = records.filtered(
            lambda rec: violations.get(rec.id)
            and not self._can_override_all(
                violations[rec.id], user_group_ids
            )
        )
        override_records = records - safe_records - blocked_records
        reason_records = override_records.filtered(
            lambda rec: any(
                item["rule"].require_reason_on_override
                for item in violations[rec.id]
            )
        )
        automatic_override_records = override_records - reason_records

        if reason:
            if blocked_records:
                raise UserError(self._blocked_error_text(blocked_records, violations))
            self._validate_override_reason(reason, override_records, violations)
            self._create_audit_logs(override_records, violations, reason)
            return self._call_original(original, records, args, kwargs)

        if automatic_override_records:
            self._create_audit_logs(
                automatic_override_records, violations, reason=""
            )

        processable_records = safe_records | automatic_override_records
        processed_result = None
        if processable_records:
            processed_result = self._call_original(
                original, processable_records, args, kwargs
            )

        if reason_records:
            return self._override_wizard_action(
                reason_records=reason_records,
                blocked_records=blocked_records,
                processed_records=processable_records,
                violations=violations,
                model_name=model_name,
                method_name=method_name,
            )

        if blocked_records:
            if not processable_records:
                raise UserError(self._blocked_error_text(blocked_records, violations))
            return self._partial_result_notification(
                processable_records, blocked_records, violations
            )

        return processed_result

    @api.model
    def _call_original(self, original, records, args, kwargs):
        return original(
            records.with_context(**{CTX_BYPASS: _INTERNAL_BYPASS_TOKEN}),
            *args,
            **kwargs
        )

    @api.model
    def _evaluate_violations(self, records, rules):
        violations = defaultdict(list)
        evaluation_context = {
            "__builtins__": {},
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
        }

        for rule in rules:
            try:
                domain = safe_eval(
                    rule.domain or "[]", {"__builtins__": {}}
                )
                targets = records.filtered_domain(domain) if domain else records
            except Exception as exc:
                _logger.exception(
                    "MarginGuard rule %s has an invalid runtime domain.",
                    rule.display_name,
                )
                raise UserError(
                    _(
                        "Margin Guard rule '%(rule)s' has an invalid domain. "
                        "Confirmation was stopped. Contact a system "
                        "administrator.\n\nTechnical detail: %(detail)s"
                    )
                    % {"rule": rule.display_name, "detail": str(exc)}
                ) from exc

            for record in targets:
                try:
                    actual = safe_eval(
                        rule.margin_formula,
                        dict(evaluation_context, record=record),
                    )
                    actual = float(actual)
                    if not math.isfinite(actual):
                        raise ValueError("result is not a finite number")
                except Exception as exc:
                    _logger.exception(
                        "MarginGuard rule %s formula failed for %s/%s.",
                        rule.display_name,
                        record._name,
                        record.id,
                    )
                    raise UserError(
                        _(
                            "Margin Guard rule '%(rule)s' could not calculate "
                            "the margin for %(record)s. Confirmation was "
                            "stopped so the order is not processed without "
                            "protection.\n\nTechnical detail: %(detail)s"
                        )
                        % {
                            "rule": rule.display_name,
                            "record": record.display_name,
                            "detail": str(exc),
                        }
                    ) from exc

                if actual < rule.threshold_pct:
                    violations[record.id].append(
                        {"rule": rule, "actual": actual}
                    )

        return violations

    @api.model
    def _can_override_all(self, record_violations, user_group_ids):
        return all(
            item["rule"].override_group_id
            and item["rule"].override_group_id.id in user_group_ids
            for item in record_violations
        )

    @api.model
    def _validate_override_reason(self, reason, records, violations):
        required_lengths = [
            item["rule"].min_reason_length
            for record in records
            for item in violations[record.id]
            if item["rule"].require_reason_on_override
        ]
        minimum = max(required_lengths or [0])
        if minimum and len(reason) < minimum:
            raise UserError(
                _("Override reason must be at least %d characters.") % minimum
            )

    @api.model
    def _create_audit_logs(self, records, violations, reason):
        if not records:
            return

        actual_user = records.env.user
        vals_list = []
        for record in records:
            for item in violations[record.id]:
                rule = item["rule"]
                vals_list.append(
                    {
                        "rule_id": rule.id,
                        "res_model": record._name,
                        "res_id": record.id,
                        "record_name": record.display_name
                        or _("Record #%s") % record.id,
                        "user_id": actual_user.id,
                        "threshold_pct": rule.threshold_pct,
                        "actual_pct": item["actual"],
                        "reason": reason,
                    }
                )

        try:
            records.env["cm_sa.margin.override.log"].sudo().with_context(
                **{CTX_AUDIT_CREATE: True}
            ).create(vals_list)
        except Exception as exc:
            _logger.exception("MarginGuard: mandatory audit log creation failed.")
            raise UserError(
                _(
                    "The margin override could not be written to the audit "
                    "log, so confirmation was cancelled. Contact a system "
                    "administrator."
                )
            ) from exc

        for record in records:
            if not hasattr(record, "message_post"):
                continue
            lines = []
            for item in violations[record.id]:
                rule = item["rule"]
                lines.append(
                    _("%(rule)s: %(actual).1f%% < %(threshold).1f%%")
                    % {
                        "rule": rule.display_name,
                        "actual": item["actual"],
                        "threshold": rule.threshold_pct,
                    }
                )
            reason_text = reason or _("Reason was not required by the rule.")
            body = Markup(
                "<p>%s</p><ul>%s</ul><p><b>%s</b> %s</p>"
            ) % (
                escape(
                    _("Margin Guard override approved by %s")
                    % actual_user.display_name
                ),
                Markup("".join("<li>%s</li>" % escape(line) for line in lines)),
                escape(_("Reason:")),
                escape(reason_text),
            )
            try:
                record.message_post(
                    body=body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:
                _logger.warning(
                    "MarginGuard: chatter message failed for %s/%s; "
                    "the immutable audit log was created.",
                    record._name,
                    record.id,
                    exc_info=True,
                )

    @api.model
    def _override_wizard_action(
        self,
        reason_records,
        blocked_records,
        processed_records,
        violations,
        model_name,
        method_name,
    ):
        involved_rules = {
            item["rule"].id
            for record in reason_records
            for item in violations[record.id]
        }
        required_lengths = [
            item["rule"].min_reason_length
            for record in reason_records
            for item in violations[record.id]
            if item["rule"].require_reason_on_override
        ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Margin Override - Reason Required"),
            "res_model": "cm_sa.margin.override.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_rule_id": (
                    next(iter(involved_rules)) if len(involved_rules) == 1 else False
                ),
                "default_model_name": model_name,
                "default_method_name": method_name,
                "default_record_id_str": ",".join(
                    str(record.id) for record in reason_records
                ),
                "default_min_length": max(required_lengths or [0]),
                "default_violation_summary": self._violation_summary(
                    reason_records, violations
                ),
                "default_processed_summary": self._processed_summary(
                    processed_records
                ),
                "default_blocked_summary": self._blocked_summary(
                    blocked_records, violations
                ),
            },
        }

    @api.model
    def _violation_summary(self, records, violations, limit=30):
        lines = []
        total = 0
        for record in records:
            for item in violations[record.id]:
                total += 1
                if len(lines) < limit:
                    lines.append(
                        _("%(record)s - %(rule)s: %(actual).1f%% < %(threshold).1f%%")
                        % {
                            "record": record.display_name,
                            "rule": item["rule"].display_name,
                            "actual": item["actual"],
                            "threshold": item["rule"].threshold_pct,
                        }
                    )
        if total > len(lines):
            lines.append(_("... and %d more violation(s).") % (total - len(lines)))
        return "\n".join(lines)

    @api.model
    def _processed_summary(self, records):
        if not records:
            return ""
        return _(
            "%(count)d selected record(s) did not require a reason and were "
            "processed normally: %(records)s"
        ) % {
            "count": len(records),
            "records": ", ".join(records.mapped("display_name")[:10]),
        }

    @api.model
    def _blocked_summary(self, records, violations):
        if not records:
            return ""
        lines = []
        for record in records[:20]:
            messages = [
                self._render_error_message(
                    item["rule"], record, item["actual"]
                )
                for item in violations[record.id]
                if not item["rule"].override_group_id
                or item["rule"].override_group_id.id
                not in set(record.env.user.all_group_ids.ids)
            ]
            lines.append("%s - %s" % (record.display_name, " | ".join(messages)))
        if len(records) > len(lines):
            lines.append(_("... and %d more blocked record(s).") % (len(records) - len(lines)))
        return "\n".join(lines)

    @api.model
    def _blocked_error_text(self, records, violations):
        return _(
            "The following selected record(s) were not confirmed by Margin "
            "Guard:\n\n%s"
        ) % self._blocked_summary(records, violations)

    @api.model
    def _render_error_message(self, rule, record, actual):
        values = {
            "model": record.display_name or record._name,
            "actual": actual,
            "threshold": rule.threshold_pct,
        }
        try:
            return rule.error_message % values
        except Exception:
            _logger.exception(
                "MarginGuard rule %s has a legacy invalid error message.",
                rule.display_name,
            )
            return _(
                "%(record)s is below the required margin "
                "(%(actual).1f%% < %(threshold).1f%%)."
            ) % {
                "record": values["model"],
                "actual": actual,
                "threshold": rule.threshold_pct,
            }

    @api.model
    def _partial_result_notification(self, processed, blocked, violations):
        message = _(
            "%(processed)d record(s) were processed normally. "
            "%(blocked)d record(s) remain unconfirmed:\n%(details)s"
        ) % {
            "processed": len(processed),
            "blocked": len(blocked),
            "details": self._blocked_summary(blocked, violations),
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Margin Guard - Partial Confirmation"),
                "message": message,
                "type": "warning",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug(
                "MarginGuard: registry signaling is unavailable; the current "
                "worker is already updated and dynamic rule values remain "
                "effective immediately.",
                exc_info=True,
            )

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            vals = dict(vals)
            if "method_name" in vals and vals["method_name"]:
                vals["method_name"] = vals["method_name"].strip()
            normalized.append(vals)
        records = super().create(normalized)
        pairs = {
            (record.model_name, record.method_name)
            for record in records.filtered("active")
        }
        self._install_active_wrappers(pairs)
        self._signal_registry()
        return records

    def write(self, vals):
        vals = dict(vals)
        if "method_name" in vals and vals["method_name"]:
            vals["method_name"] = vals["method_name"].strip()
        result = super().write(vals)
        pairs = {
            (record.model_name, record.method_name)
            for record in self.filtered("active")
        }
        self._install_active_wrappers(pairs)
        if {"active", "model_id", "method_name"}.intersection(vals):
            self._signal_registry()
        return result

    def unlink(self):
        rules_with_logs = self.sudo().filtered("log_ids")
        if rules_with_logs:
            raise ValidationError(
                _(
                    "Rules with Margin Override audit logs cannot be deleted: "
                    "%s. Archive them instead."
                )
                % ", ".join(rules_with_logs.mapped("display_name"))
            )
        result = super().unlink()
        self._signal_registry()
        return result

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Margin Override Log"),
            "res_model": "cm_sa.margin.override.log",
            "view_mode": "list,pivot,form",
            "domain": [("rule_id", "=", self.id)],
            "context": {"create": False, "edit": False, "delete": False},
        }
