"""Registry-load wrapper on sale.order.action_confirm that blocks D-band
customers when the active config has require_rule=True. Pattern mirrors
cm_sa_so_confirm_guard / cm_sa_credit_hold."""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_SCORE_MARKER = "_cm_sa_payment_score_wrapper"
_SCORE_ORIGINAL = "_cm_sa_payment_score_original"


class PaymentScoreGuardInstaller(models.AbstractModel):
    _name = "cm_sa.payment_score.guard.installer"
    _description = "Payment Score SO Guard Installer"

    def _register_hook(self):
        super()._register_hook()
        if "sale.order" not in self.env.registry:
            return
        try:
            cls = type(self.env["sale.order"])
        except Exception:
            return
        original = getattr(cls, "action_confirm", None)
        if original is None or not callable(original):
            return
        if getattr(original, _SCORE_MARKER, False):
            original = getattr(original, _SCORE_ORIGINAL, original)

        wrapper = self._build_wrapper(original)
        setattr(wrapper, _SCORE_MARKER, True)
        setattr(wrapper, _SCORE_ORIGINAL, original)
        wrapper.__name__ = "action_confirm"
        wrapper.__qualname__ = "%s.action_confirm" % cls.__name__
        setattr(cls, "action_confirm", wrapper)
        _logger.info("payment_score: sale.order.action_confirm wrapper installed.")

    @staticmethod
    def _build_wrapper(original):
        def guarded(self, *args, **kwargs):
            Config = self.env["cm_sa.payment_score.config"].sudo()
            config = Config._get_active()
            if not config or not config.require_rule:
                return original(self, *args, **kwargs)
            # Admins bypass.
            if self.env.user.has_group("base.group_system"):
                return original(self, *args, **kwargs)
            bad = self.env["res.partner"]
            for order in self:
                partner = order.partner_id
                if partner and partner.payment_score_band == "D":
                    bad |= partner
            if bad:
                names = ", ".join(bad.mapped("display_name"))
                # Best-effort chatter log on each affected sale order.
                for order in self:
                    if order.partner_id in bad and hasattr(order, "message_post"):
                        try:
                            order.message_post(
                                body=_(
                                    "Payment score guard: confirm blocked — "
                                    "customer is band D."
                                ),
                                message_type="comment",
                                subtype_xmlid="mail.mt_note",
                            )
                        except Exception:
                            pass
                raise UserError(_(
                    "This sale order cannot be confirmed because the "
                    "customer is on payment-score band D: %s\n\n"
                    "Ask an administrator to override, or resolve the A/R "
                    "issue and recompute the score."
                ) % names)
            return original(self, *args, **kwargs)
        return guarded
