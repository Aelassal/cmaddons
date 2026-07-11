import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

_AUDIT_MARKER = "_cm_sa_reset_audit_wrapper"
_AUDIT_ORIGINAL = "_cm_sa_reset_audit_original"

# Context key. When the reason wizard re-invokes the reset method, it sets
# this. Wrappers consume the value and skip the "reason required" check.
CTX_REASON = "cm_sa_reset_audit_reason"
# Bypass flag for defensive internal calls.
CTX_BYPASS = "cm_sa_reset_audit_bypass"

# These wrappers are installed at registry load even if no rule exists yet.
# The wrapper reads rules from the database at click time, so a newly-created
# rule for one of these targets works immediately without module upgrade.
DEFAULT_RESET_TARGETS = [
    ("account.move", "button_draft"),
    ("sale.order", "action_draft"),
    ("purchase.order", "button_draft"),
    ("purchase.order", "action_draft"),
    ("stock.picking", "action_cancel_draft"),
]


class CmSaResetAuditRule(models.Model):
    _name = "cm_sa.reset_audit.rule"
    _description = "Reset-to-Draft Audit Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "model_name, method_name, id"

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
        string="Reset Method",
        required=True,
        default="action_draft",
        tracking=True,
        help="Name of the reset-to-draft method on the target model. Common:\n"
             "  - action_draft    (sale.order, purchase.order)\n"
             "  - button_draft    (account.move, purchase.order)\n"
             "  - action_cancel_draft\n"
             "Custom reset buttons from your own modules also work, but the "
             "first wrapper installation may require a registry reload if the "
             "target is not one of the built-in targets.",
    )
    require_reason = fields.Boolean(
        default=True,
        tracking=True,
        help="If enabled, clicking Reset opens a wizard asking the user for a "
             "reason before the reset runs.",
    )
    required_group_id = fields.Many2one(
        "res.groups",
        string="Required Group",
        tracking=True,
        help="Optional: only users in this group may reset records matching "
             "this rule. Others see an access error.",
    )
    domain = fields.Char(
        default="[]",
        tracking=True,
        help="Optional domain to limit the rule to a subset of records.\n"
             "Example: [('amount_total', '>', 1000)]",
    )
    min_reason_length = fields.Integer(
        default=10,
        tracking=True,
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
    # Registry hook / dynamic wrappers
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return

        targets = set(DEFAULT_RESET_TARGETS)

        # Also install wrappers for rules that already exist at registry load.
        # This keeps support for custom model/method combinations.
        try:
            rules = self.sudo().search([("active", "=", True)])
            for rule in rules:
                if rule.model_name and rule.method_name:
                    targets.add((rule.model_name, rule.method_name.strip()))
        except Exception:
            _logger.exception(
                "ResetAudit: could not load rules; only default wrappers will be installed."
            )

        installed = 0
        for model_name, method_name in sorted(targets):
            if self._install_wrapper(model_name, method_name):
                installed += 1

        if installed:
            _logger.info("ResetAudit: installed %d dynamic wrapper(s).", installed)

    def _table_exists(self):
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (self._table,),
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    def _install_wrapper(self, model_name, method_name):
        """Install/refresh one wrapper in the current registry.

        The wrapper reads matching rules at execution time. This is the key
        change that makes new rules effective immediately when the target
        method has already been wrapped.
        """
        method_name = (method_name or "").strip()
        if not model_name or not method_name:
            return False
        if model_name not in self.env.registry:
            _logger.warning(
                "ResetAudit: target model %s is not available; wrapper skipped.",
                model_name,
            )
            return False

        cls = type(self.env[model_name])
        original = getattr(cls, method_name, None)
        if original is None or not callable(original):
            _logger.warning(
                "ResetAudit: %s.%s not found; wrapper skipped.",
                model_name, method_name,
            )
            return False

        if getattr(original, _AUDIT_MARKER, False):
            original = getattr(original, _AUDIT_ORIGINAL, original)

        wrapper = self._build_wrapper(model_name, method_name, original)
        setattr(wrapper, _AUDIT_MARKER, True)
        setattr(wrapper, _AUDIT_ORIGINAL, original)
        wrapper.__name__ = method_name
        wrapper.__qualname__ = f"{cls.__name__}.{method_name}"
        setattr(cls, method_name, wrapper)
        return True

    @staticmethod
    def _build_wrapper(model_name, method_name, original):
        def audited(self, *args, **kwargs):
            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            Rule = self.env["cm_sa.reset_audit.rule"].sudo()
            Log = self.env["cm_sa.reset_audit.log"].sudo()

            rules = Rule.search([
                ("active", "=", True),
                ("model_name", "=", model_name),
                ("method_name", "=", method_name),
            ], order="id")
            if not rules:
                return original(self, *args, **kwargs)

            reason_from_ctx = self.env.context.get(CTX_REASON) or ""
            targets_by_rule = []

            for rule in rules:
                try:
                    domain = safe_eval(rule.domain or "[]", {"__builtins__": {}})
                except Exception as exc:
                    raise UserError(
                        _("Invalid reset-audit domain on rule %(rule)s: %(error)s") % {
                            "rule": rule.display_name,
                            "error": exc,
                        }
                    )

                targets = self.filtered_domain(domain) if domain else self
                if not targets:
                    continue
                targets_by_rule.append((rule, targets))

                # Group enforcement
                user_group_ids = get_user_groups(self.env.user).ids

                if rule.required_group_id and rule.required_group_id.id not in user_group_ids:
                    raise UserError(_(
                        "You are not allowed to reset %(model)s records to draft. "
                        "Required group: %(group)s."
                    ) % {
                                        "model": model_name,
                                        "group": rule.required_group_id.display_name,
                                    })

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

                # Reason length check when the wizard or an API caller supplied it.
                if (rule.require_reason and rule.min_reason_length
                        and len(reason_from_ctx.strip()) < rule.min_reason_length):
                    raise UserError(_(
                        "Reason must be at least %d characters long."
                    ) % rule.min_reason_length)

            if not targets_by_rule:
                return original(self, *args, **kwargs)

            # Run original once, then log the targets captured before the reset.
            result = original(self, *args, **kwargs)

            for rule, targets in targets_by_rule:
                for record in targets:
                    try:
                        Log.with_context(**{CTX_BYPASS: True}).create({
                            "rule_id": rule.id,
                            "res_model": model_name,
                            "res_id": record.id,
                            "record_name": record.display_name or _("Record #%s") % record.id,
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
                                    "Reset-to-Draft Audit [%(rule)s] by %(user)s. Reason: %(reason)s"
                                ) % {
                                    "rule": rule.name,
                                    "user": self.env.user.display_name,
                                    "reason": reason_from_ctx or _("(none)"),
                                },
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                            )
                        except Exception:
                            _logger.debug(
                                "ResetAudit: could not post chatter note for %s/%s",
                                model_name, record.id,
                                exc_info=True,
                            )
            return result

        def get_user_groups(user):
            user = user.sudo()

            if "groups_id" in user._fields:
                return user.groups_id

            if "group_ids" in user._fields:
                return user.group_ids

            Groups = user.env["res.groups"].sudo()
            if "users" in Groups._fields:
                return Groups.search([("users", "in", user.id)])

            user.env.cr.execute(
                "SELECT gid FROM res_groups_users_rel WHERE uid = %s",
                (user.id,),
            )
            return Groups.browse([row[0] for row in user.env.cr.fetchall()])

        return audited

    # ------------------------------------------------------------------
    # CRUD — make new rules effective immediately in the current registry
    # ------------------------------------------------------------------
    def _ensure_wrappers_for_records(self):
        installed = 0
        for rec in self:
            if rec.active and rec.model_name and rec.method_name:
                if rec._install_wrapper(rec.model_name, rec.method_name):
                    installed += 1
        if installed:
            _logger.info("ResetAudit: refreshed %d wrapper(s) from rule change.", installed)

    def _signal_registry(self):
        # Keep the old signal for environments that reload registries on changes,
        # but the current worker is patched immediately by _ensure_wrappers_for_records.
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug(
                "ResetAudit: registry.signal_changes() unavailable; current worker "
                "was patched directly."
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_wrappers_for_records()
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        structural = {"active", "model_id", "method_name"}
        if structural.intersection(vals):
            self._ensure_wrappers_for_records()
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
