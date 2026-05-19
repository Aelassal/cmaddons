import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

_AUDIT_MARKER = "_cm_sa_reset_audit_wrapper"
_AUDIT_ORIGINAL = "_cm_sa_reset_audit_original"

# Context key. When the reason wizard re-invokes the original method, it sets
# this. Wrappers consume the value and skip the "reason required" check.
CTX_REASON = "cm_sa_reset_audit_reason"
# Bypass flag. When a log row is being written, internal operations must not
# trigger the wrapper recursively (they don't in practice, but defensive).
CTX_BYPASS = "cm_sa_reset_audit_bypass"


class CmSaResetAuditRule(models.Model):
    _name = "cm_sa.reset_audit.rule"
    _description = "Reset-to-Draft Audit Rule"
    _order = "model_name, method_name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        index=True,
        string="Technical Model Name",
    )
    method_name = fields.Char(
        string="Reset Method",
        required=True,
        default="action_draft",
        help="Name of the reset-to-draft method on the target model. Common:\n"
             "  - action_draft    (sale.order, purchase.order)\n"
             "  - button_draft    (account.move, purchase.order)\n"
             "  - action_cancel_draft\n"
             "Custom reset buttons from your own modules also work.",
    )
    require_reason = fields.Boolean(
        default=True,
        help="If enabled, clicking Reset opens a wizard asking the user for a "
             "reason before the reset runs.",
    )
    required_group_id = fields.Many2one(
        "res.groups",
        string="Required Group",
        help="Optional: only users in this group may reset records matching "
             "this rule. Others see an access error.",
    )
    domain = fields.Char(
        default="[]",
        help="Optional domain to limit the rule to a subset of records.\n"
             "Example: [('amount_total', '>', 1000)]",
    )
    min_reason_length = fields.Integer(
        default=10,
        help="Minimum characters required in the reason. 0 disables the check.",
    )

    log_ids = fields.One2many("cm_sa.reset_audit.log", "rule_id", readonly=True)
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A reset-audit rule with this name already exists.",
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
                )
            if not isinstance(value, list):
                raise ValidationError(_("Domain must evaluate to a list."))

    @api.constrains("method_name")
    def _check_method_name(self):
        for rec in self:
            if not rec.method_name or not rec.method_name.strip():
                raise ValidationError(_("Method Name is required."))

    @api.constrains("min_reason_length")
    def _check_min_reason_length(self):
        for rec in self:
            if rec.min_reason_length < 0:
                raise ValidationError(_("Minimum reason length must be >= 0."))

    # ------------------------------------------------------------------
    # Registry hook — wrap configured methods at load time
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return

        try:
            rules = self.sudo().search([("active", "=", True)])
        except Exception:
            _logger.exception(
                "ResetAudit: could not load rules; no wrappers installed."
            )
            return

        grouped = {}
        for rule in rules:
            if not rule.model_name or rule.model_name not in self.env.registry:
                _logger.warning(
                    "ResetAudit rule %r targets unknown model %r — skipped.",
                    rule.name, rule.model_name,
                )
                continue
            method_name = (rule.method_name or "").strip()
            if not method_name:
                continue
            grouped.setdefault((rule.model_name, method_name), []).append(rule.id)

        installed = 0
        for (model_name, method_name), rule_ids in grouped.items():
            cls = type(self.env[model_name])
            original = getattr(cls, method_name, None)
            if original is None or not callable(original):
                _logger.warning(
                    "ResetAudit: %s.%s not found — %d rule(s) skipped.",
                    model_name, method_name, len(rule_ids),
                )
                continue
            if getattr(original, _AUDIT_MARKER, False):
                original = getattr(original, _AUDIT_ORIGINAL, original)

            wrapper = self._build_wrapper(
                model_name, method_name, rule_ids, original,
            )
            setattr(wrapper, _AUDIT_MARKER, True)
            setattr(wrapper, _AUDIT_ORIGINAL, original)
            wrapper.__name__ = method_name
            wrapper.__qualname__ = f"{cls.__name__}.{method_name}"
            setattr(cls, method_name, wrapper)
            installed += 1

        if installed:
            _logger.info("ResetAudit: installed %d wrapper(s).", installed)

    def _table_exists(self):
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (self._table,),
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    @staticmethod
    def _build_wrapper(model_name, method_name, rule_ids, original):
        def audited(self, *args, **kwargs):
            Rule = self.env["cm_sa.reset_audit.rule"].sudo()
            Log = self.env["cm_sa.reset_audit.log"].sudo()

            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            rules = Rule.browse(rule_ids).exists().filtered("active")
            if not rules:
                return original(self, *args, **kwargs)

            reason_from_ctx = self.env.context.get(CTX_REASON) or ""
            for rule in rules:
                try:
                    domain = safe_eval(rule.domain or "[]", {"__builtins__": {}})
                except Exception:
                    _logger.exception(
                        "ResetAudit rule %s: invalid domain, skipping.", rule.name,
                    )
                    continue
                targets = self.filtered_domain(domain) if domain else self
                if not targets:
                    continue

                # Group enforcement
                if rule.required_group_id and rule.required_group_id not in self.env.user.groups_id:
                    raise UserError(_(
                        "You are not allowed to reset %s records to draft. "
                        "Required group: %s."
                    ) % (model_name, rule.required_group_id.display_name))

                # Reason enforcement — open wizard if none supplied
                if rule.require_reason and not reason_from_ctx:
                    return {
                        "type": "ir.actions.act_window",
                        "name": _("Reason for Reset"),
                        "res_model": "cm_sa.reset_audit.wizard",
                        "view_mode": "form",
                        "target": "new",
                        "context": {
                            "default_rule_id": rule.id,
                            "default_model_name": model_name,
                            "default_method_name": method_name,
                            "default_record_ids": [(6, 0, targets.ids)],
                            "default_min_length": rule.min_reason_length,
                        },
                    }

                # Reason length check (in case caller passed it directly)
                if (rule.require_reason and rule.min_reason_length
                        and len(reason_from_ctx.strip()) < rule.min_reason_length):
                    raise UserError(_(
                        "Reason must be at least %d characters long."
                    ) % rule.min_reason_length)

            # All rules passed — run original and log
            result = original(self, *args, **kwargs)

            for rule in rules:
                try:
                    domain = safe_eval(rule.domain or "[]", {"__builtins__": {}})
                except Exception:
                    continue
                targets = self.filtered_domain(domain) if domain else self
                for record in targets:
                    try:
                        Log.with_context(**{CTX_BYPASS: True}).create({
                            "rule_id": rule.id,
                            "res_model": model_name,
                            "res_id": record.id,
                            "record_name": record.display_name or
                                _("Record #%s") % record.id,
                            "method_name": method_name,
                            "user_id": self.env.user.id,
                            "reason": reason_from_ctx,
                        })
                    except Exception:
                        _logger.exception(
                            "ResetAudit: failed to log reset of %s/%s",
                            model_name, record.id,
                        )
                    if hasattr(record, "message_post"):
                        try:
                            record.message_post(
                                body=_(
                                    "Reset-to-Draft Audit [%(rule)s] by "
                                    "<b>%(user)s</b>. Reason: %(reason)s"
                                ) % {
                                    "rule": rule.name,
                                    "user": self.env.user.display_name,
                                    "reason": reason_from_ctx or _("(none)"),
                                },
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                            )
                        except Exception:
                            pass
            return result

        return audited

    # ------------------------------------------------------------------
    # CRUD — signal registry so wrappers refresh
    # ------------------------------------------------------------------
    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug(
                "ResetAudit: registry.signal_changes() unavailable; "
                "a service restart may be needed for the change to propagate."
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        structural = {"active", "model_id", "model_name", "method_name"}
        if structural.intersection(vals):
            self._signal_registry()
        return res

    def unlink(self):
        res = super().unlink()
        self._signal_registry()
        return res

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reset Audit Log"),
            "res_model": "cm_sa.reset_audit.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
