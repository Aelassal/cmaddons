import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

_MARGIN_MARKER = "_cm_sa_margin_guard_wrapper"
_MARGIN_ORIGINAL = "_cm_sa_margin_guard_original"

CTX_REASON = "cm_sa_margin_override_reason"
CTX_BYPASS = "cm_sa_margin_guard_bypass"

DEFAULT_SO_FORMULA = (
    "(record.amount_untaxed - sum(line.purchase_price * line.product_uom_qty "
    "for line in record.order_line)) / record.amount_untaxed * 100 "
    "if record.amount_untaxed else 100"
)


class CmSaMarginGuardRule(models.Model):
    _name = "cm_sa.margin.guard.rule"
    _description = "Sale-Order Margin Guard Rule"
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
        string="Method to Guard",
        required=True,
        default="action_confirm",
        help="Name of the method to wrap. For sale.order this is "
             "usually action_confirm. Custom buttons work too.",
    )
    margin_formula = fields.Text(
        required=True,
        default=DEFAULT_SO_FORMULA,
        help="Python expression evaluated against 'record'. Must return "
             "a number — the margin percentage. Default formula computes "
             "gross margin % from purchase_price on sale.order lines.",
    )
    threshold_pct = fields.Float(
        string="Minimum Margin %",
        required=True,
        default=10.0,
        help="Records below this percentage trigger the guard.",
    )
    domain = fields.Char(
        default="[]",
        help="Optional Odoo domain to scope the rule to a subset of records.",
    )
    override_group_id = fields.Many2one(
        "res.groups",
        string="Override Group",
        help="Members of this group may confirm below-threshold records "
             "after supplying a reason. Leave empty to block all below-"
             "threshold confirmations unconditionally.",
    )
    require_reason_on_override = fields.Boolean(
        default=True,
        help="When on, a wizard asks the override-group user for a reason "
             "before the confirm runs.",
    )
    min_reason_length = fields.Integer(
        default=10,
        help="Minimum characters required in the override reason.",
    )
    error_message = fields.Char(
        default="This %(model)s is below the required margin "
                "(%(actual).1f%% < %(threshold).1f%%). Override blocked.",
        required=True,
        help="Placeholders: %(model)s, %(actual).1f, %(threshold).1f",
    )

    log_ids = fields.One2many("cm_sa.margin.override.log", "rule_id", readonly=True)
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
                )
            if not isinstance(value, list):
                raise ValidationError(_("Domain must evaluate to a list."))

    @api.constrains("margin_formula")
    def _check_formula(self):
        for rec in self:
            if not rec.margin_formula or not rec.margin_formula.strip():
                raise ValidationError(_("Margin Formula is required."))

    @api.constrains("threshold_pct")
    def _check_threshold(self):
        for rec in self:
            if rec.threshold_pct < -1000 or rec.threshold_pct > 1000:
                raise ValidationError(_(
                    "Threshold must be between -1000 and 1000."
                ))

    # ------------------------------------------------------------------
    # Registry hook
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return

        try:
            rules = self.sudo().search([("active", "=", True)])
        except Exception:
            _logger.exception(
                "MarginGuard: could not load rules; no wrappers installed."
            )
            return

        grouped = {}
        for rule in rules:
            if not rule.model_name or rule.model_name not in self.env.registry:
                _logger.warning(
                    "MarginGuard rule %r targets unknown model %r — skipped.",
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
                    "MarginGuard: %s.%s not found — %d rule(s) skipped.",
                    model_name, method_name, len(rule_ids),
                )
                continue
            if getattr(original, _MARGIN_MARKER, False):
                original = getattr(original, _MARGIN_ORIGINAL, original)

            wrapper = self._build_wrapper(
                model_name, method_name, rule_ids, original,
            )
            setattr(wrapper, _MARGIN_MARKER, True)
            setattr(wrapper, _MARGIN_ORIGINAL, original)
            wrapper.__name__ = method_name
            wrapper.__qualname__ = f"{cls.__name__}.{method_name}"
            setattr(cls, method_name, wrapper)
            installed += 1

        if installed:
            _logger.info("MarginGuard: installed %d wrapper(s).", installed)

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
        def guarded(self, *args, **kwargs):
            Rule = self.env["cm_sa.margin.guard.rule"].sudo()
            Log = self.env["cm_sa.margin.override.log"].sudo()

            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            rules = Rule.browse(rule_ids).exists().filtered("active")
            if not rules:
                return original(self, *args, **kwargs)

            reason_from_ctx = (self.env.context.get(CTX_REASON) or "").strip()

            for rule in rules:
                try:
                    domain = safe_eval(rule.domain or "[]", {"__builtins__": {}})
                except Exception:
                    _logger.exception(
                        "MarginGuard rule %s: invalid domain, skipping.",
                        rule.name,
                    )
                    continue

                targets = self.filtered_domain(domain) if domain else self
                for record in targets:
                    try:
                        actual = safe_eval(
                            rule.margin_formula,
                            {
                                "__builtins__": {},
                                "record": record,
                                "sum": sum,
                                "min": min,
                                "max": max,
                                "abs": abs,
                                "round": round,
                            },
                        )
                        actual = float(actual)
                    except Exception as exc:
                        _logger.warning(
                            "MarginGuard rule %s: formula failed for %s/%s: %s",
                            rule.name, model_name, record.id, exc,
                        )
                        continue

                    if actual >= rule.threshold_pct:
                        continue  # OK

                    # Below threshold — check override group
                    in_override = (
                        rule.override_group_id
                        and rule.override_group_id in self.env.user.groups_id
                    )
                    if not in_override:
                        raise UserError(
                            rule.error_message % {
                                "model": record.display_name or model_name,
                                "actual": actual,
                                "threshold": rule.threshold_pct,
                            }
                        )

                    # Override-group user: require reason if configured and
                    # not already supplied.
                    if rule.require_reason_on_override and not reason_from_ctx:
                        return {
                            "type": "ir.actions.act_window",
                            "name": _("Margin Override — Reason Required"),
                            "res_model": "cm_sa.margin.override.wizard",
                            "view_mode": "form",
                            "target": "new",
                            "context": {
                                "default_rule_id": rule.id,
                                "default_model_name": model_name,
                                "default_method_name": method_name,
                                "default_record_id_str": ",".join(
                                    str(r.id) for r in targets
                                ),
                                "default_actual_margin": actual,
                                "default_threshold": rule.threshold_pct,
                                "default_min_length": rule.min_reason_length,
                            },
                        }

                    if (rule.require_reason_on_override
                            and rule.min_reason_length
                            and len(reason_from_ctx) < rule.min_reason_length):
                        raise UserError(_(
                            "Override reason must be at least %d characters."
                        ) % rule.min_reason_length)

                    # Log the override
                    try:
                        Log.with_context(**{CTX_BYPASS: True}).create({
                            "rule_id": rule.id,
                            "res_model": model_name,
                            "res_id": record.id,
                            "record_name": record.display_name or
                                _("Record #%s") % record.id,
                            "user_id": self.env.user.id,
                            "threshold_pct": rule.threshold_pct,
                            "actual_pct": actual,
                            "reason": reason_from_ctx,
                        })
                    except Exception:
                        _logger.exception(
                            "MarginGuard: log write failed for %s/%s",
                            model_name, record.id,
                        )
                    if hasattr(record, "message_post"):
                        try:
                            record.message_post(
                                body=_(
                                    "Margin Guard override by <b>%(user)s</b>: "
                                    "%(actual).1f%% < %(threshold).1f%% "
                                    "threshold. Reason: %(reason)s"
                                ) % {
                                    "user": self.env.user.display_name,
                                    "actual": actual,
                                    "threshold": rule.threshold_pct,
                                    "reason": reason_from_ctx or _("(none)"),
                                },
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                            )
                        except Exception:
                            pass

            return original(self, *args, **kwargs)

        return guarded

    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug(
                "MarginGuard: registry.signal_changes() unavailable; "
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
            "name": _("Margin Override Log"),
            "res_model": "cm_sa.margin.override.log",
            "view_mode": "list,pivot,form",
            "domain": [("rule_id", "=", self.id)],
        }
