import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Sentinel attribute set on every wrapper we install. Lets us recognise our
# own wrappers and unwind them on a re-register, so a second registry build
# in the same process doesn't stack wrappers on top of each other.
_GUARD_MARKER = "_cm_sa_confirm_guard_wrapper"
_GUARD_ORIGINAL = "_cm_sa_confirm_guard_original"


class ConfirmGuard(models.Model):
    _name = "cm_sa.confirm.guard"
    _description = "Confirm-Time Field Guard Rule"
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
        string="Technical Model Name",
        related="model_id.model",
        store=True,
        readonly=True,
        index=True,
    )
    method_name = fields.Char(
        string="Method to Guard",
        required=True,
        default="action_confirm",
        help="Name of the button method to wrap. Common values:\n"
             "  - action_confirm   (sale.order, purchase.order)\n"
             "  - action_post      (account.move)\n"
             "  - button_validate  (stock.picking)\n"
             "Custom buttons from your own modules also work.",
    )
    required_field_ids = fields.Many2many(
        "ir.model.fields",
        string="Required Fields",
        domain="[('model_id', '=', model_id)]",
        required=True,
        help="Fields that must be filled on each matching record before the "
             "method is allowed to run.",
    )
    domain = fields.Char(
        default="[]",
        help="Optional Odoo domain to restrict the rule to a subset of records. "
             "Example: [('amount_total', '>', 1000)]",
    )
    error_message = fields.Char(
        default="The following fields are required to confirm: %s",
        required=True,
        help="Use a single %s placeholder — it is replaced with a comma-separated "
             "list of the missing field labels.",
    )

    _name_unique = models.Constraint(
        "unique(name)",
        "A confirm-guard rule with this name already exists.",
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("domain")
    def _check_domain(self):
        for rec in self:
            try:
                value = safe_eval(rec.domain or "[]")
            except Exception as exc:
                raise ValidationError(
                    _("Domain is not a valid Python expression: %s") % exc
                )
            if not isinstance(value, list):
                raise ValidationError(_("Domain must evaluate to a list."))

    @api.constrains("error_message")
    def _check_error_message(self):
        for rec in self:
            if rec.error_message and "%s" not in rec.error_message:
                raise ValidationError(_(
                    "Error Message must contain a single %s placeholder for "
                    "the missing field list."
                ))

    @api.constrains("method_name")
    def _check_method_name(self):
        for rec in self:
            if not rec.method_name or not rec.method_name.strip():
                raise ValidationError(_("Method Name is required."))

    # ------------------------------------------------------------------
    # Registry hook — wrap configured methods at load time
    # ------------------------------------------------------------------
    def _register_hook(self):
        """Install confirm-guard wrappers on every active rule's target.

        Odoo 19 calls this on each model class once per registry build. Our
        strategy:

        1. Read every active rule.
        2. For each, look up ``Model = self.env[rule.model_name]`` and
           ``getattr(type(Model), rule.method_name, None)``.
        3. If found, replace it on the class with a wrapper that holds a
           reference to the previous bound method (the "original"), so
           multiple rules on the same ``(model, method)`` pair chain
           naturally.
        4. Mark every wrapper with a sentinel attribute so a second
           ``_register_hook`` call (e.g. after a registry reload) can unwind
           the previous stack instead of growing it forever.
        """
        super()._register_hook()
        # First pass on a brand-new install: our schema may not exist yet.
        if not self._table_exists():
            return

        try:
            rules = self.sudo().search([("active", "=", True)])
        except Exception:
            _logger.exception(
                "ConfirmGuard: could not load rules; no wrappers installed."
            )
            return

        # Group rules by (model_name, method_name) so we register one wrapper
        # per target and let the wrapper iterate its rules in order.
        grouped = {}
        for rule in rules:
            if not rule.model_name or rule.model_name not in self.env.registry:
                _logger.warning(
                    "ConfirmGuard rule %r targets unknown model %r — skipped.",
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
                    "ConfirmGuard: %s.%s not found — %d rule(s) skipped.",
                    model_name, method_name, len(rule_ids),
                )
                continue

            # If we already wrapped this slot in a previous _register_hook
            # call (same process, registry rebuild), unwind to the real
            # original first so we don't stack wrappers indefinitely.
            if getattr(original, _GUARD_MARKER, False):
                original = getattr(original, _GUARD_ORIGINAL, original)

            wrapper = self._build_wrapper(model_name, method_name, rule_ids, original)
            setattr(wrapper, _GUARD_MARKER, True)
            setattr(wrapper, _GUARD_ORIGINAL, original)
            wrapper.__name__ = method_name
            wrapper.__qualname__ = f"{cls.__name__}.{method_name}"
            setattr(cls, method_name, wrapper)
            installed += 1

        if installed:
            _logger.info("ConfirmGuard: installed %d wrapper(s).", installed)

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
        """Return a closure that enforces every rule in ``rule_ids`` and
        then calls ``original`` (the previous bound method on the class).

        Rule attributes (required fields, domain, error message) are read
        fresh on every call, so admins can tweak them without restarting
        Odoo. Only structural changes — model / method / active flag —
        require a registry reload to install or remove the wrapper itself.
        """
        def guarded(self, *args, **kwargs):
            Guard = self.env["cm_sa.confirm.guard"].sudo()
            for rule in Guard.browse(rule_ids).exists():
                if not rule.active:
                    continue
                try:
                    domain = safe_eval(rule.domain or "[]")
                except Exception:
                    _logger.exception(
                        "ConfirmGuard rule %s: invalid domain, skipping.",
                        rule.name,
                    )
                    continue

                targets = self.filtered_domain(domain) if domain else self
                for record in targets:
                    missing = []
                    for field in rule.required_field_ids:
                        fname = field.name
                        if fname not in record._fields:
                            continue
                        if not record[fname]:
                            missing.append(field.field_description or fname)
                    if missing:
                        label = record.display_name or (_("Record #%s") % record.id)
                        raise UserError(
                            ("[%s] " % label)
                            + (rule.error_message % ", ".join(missing))
                        )
            return original(self, *args, **kwargs)

        return guarded

    # ------------------------------------------------------------------
    # CRUD — signal the registry so wrappers refresh on the next request
    # ------------------------------------------------------------------
    def _signal_registry(self):
        """Best-effort registry signal so other workers reload wrappers."""
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug(
                "ConfirmGuard: registry.signal_changes() unavailable; "
                "a service restart may be needed for the change to propagate."
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Only structural changes require a registry rebuild. Edits to
        # required_field_ids / domain / error_message are read fresh on
        # every call, so they take effect without a reload.
        structural = {"active", "model_id", "model_name", "method_name"}
        if structural.intersection(vals):
            self._signal_registry()
        return res

    def unlink(self):
        res = super().unlink()
        self._signal_registry()
        return res
