"""Registry-load wrappers that enforce credit holds on sale/purchase/stock
confirm methods. Pattern mirrors cm_sa_so_confirm_guard."""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_HOLD_MARKER = "_cm_sa_credit_hold_wrapper"
_HOLD_ORIGINAL = "_cm_sa_credit_hold_original"

# (model_name, method_name, [partner_field_names])
_TARGETS = [
    ("sale.order", "action_confirm",
     ["partner_id", "partner_invoice_id", "partner_shipping_id"]),
    ("purchase.order", "button_confirm", ["partner_id"]),
    ("stock.picking", "button_validate", ["partner_id"]),
]


class CreditHoldGuardInstaller(models.AbstractModel):
    _name = "cm_sa.credit_hold.guard.installer"
    _description = "Credit Hold Registry Wrapper Installer"

    def _register_hook(self):
        super()._register_hook()
        for model_name, method_name, partner_fields in _TARGETS:
            if model_name not in self.env.registry:
                continue
            try:
                cls = type(self.env[model_name])
            except Exception:
                continue
            original = getattr(cls, method_name, None)
            if original is None or not callable(original):
                continue
            if getattr(original, _HOLD_MARKER, False):
                original = getattr(original, _HOLD_ORIGINAL, original)

            wrapper = self._build_wrapper(
                model_name, method_name, partner_fields, original,
            )
            setattr(wrapper, _HOLD_MARKER, True)
            setattr(wrapper, _HOLD_ORIGINAL, original)
            wrapper.__name__ = method_name
            wrapper.__qualname__ = "%s.%s" % (cls.__name__, method_name)
            setattr(cls, method_name, wrapper)
        _logger.info("credit_hold: wrappers installed.")

    @staticmethod
    def _build_wrapper(model_name, method_name, partner_fields, original):
        def guarded(self, *args, **kwargs):
            for record in self:
                held = record.env["res.partner"]
                for fname in partner_fields:
                    if fname not in record._fields:
                        continue
                    partner = record[fname]
                    if partner and partner.is_credit_held:
                        held |= partner
                if held:
                    # log block attempt on each partner
                    Log = record.env["cm_sa.credit_hold.log"].sudo()
                    for partner in held:
                        Log.create({
                            "partner_id": partner.id,
                            "event": "block_triggered",
                            "reason": partner.credit_hold_reason or "",
                            "by_user_id": record.env.user.id,
                            "ref_model": model_name,
                            "ref_id": record.id,
                        })
                    names = ", ".join(held.mapped("display_name"))
                    reasons = "\n".join(
                        "- %s: %s" % (p.display_name, p.credit_hold_reason or "(no reason)")
                        for p in held
                    )
                    release_line = ""
                    for p in held:
                        if p.credit_hold_expected_release:
                            release_line += _(
                                "\n%s expected release: %s"
                            ) % (p.display_name, p.credit_hold_expected_release)
                    raise UserError(_(
                        "This action is blocked because the following "
                        "partner(s) are on credit hold: %(names)s\n\n%(reasons)s%(rel)s"
                    ) % {"names": names, "reasons": reasons, "rel": release_line})
            return original(self, *args, **kwargs)
        return guarded
