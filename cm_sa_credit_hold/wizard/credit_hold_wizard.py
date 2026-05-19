from odoo import _, fields, models
from odoo.exceptions import UserError


class CmSaCreditHoldWizard(models.TransientModel):
    _name = "cm_sa.credit_hold.wizard"
    _description = "Credit Hold Wizard"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
    )
    mode = fields.Selection(
        [("hold", "Place on hold"), ("release", "Release hold")],
        required=True,
        default="hold",
    )
    reason = fields.Text(
        required=True,
        help="Explain why. The reason is displayed to anyone who tries to "
             "confirm a SO/PO/picking against this partner, and is logged.",
    )
    expected_release = fields.Date()

    def action_confirm(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError(_("No partner selected."))
        Log = self.env["cm_sa.credit_hold.log"].sudo()
        if self.mode == "hold":
            if partner.is_credit_held:
                raise UserError(_("This partner is already on hold."))
            partner.sudo().write({
                "is_credit_held": True,
                "credit_hold_reason": self.reason,
                "credit_hold_applied_at": fields.Datetime.now(),
                "credit_hold_applied_by": self.env.user.id,
                "credit_hold_expected_release": self.expected_release or False,
            })
            Log.create({
                "partner_id": partner.id,
                "event": "hold_applied",
                "reason": self.reason,
                "by_user_id": self.env.user.id,
            })
            partner.message_post(
                body=_(
                    "<b>Placed on credit hold</b> by %(by)s.<br/>"
                    "Reason: %(reason)s<br/>Expected release: %(rel)s"
                ) % {
                    "by": self.env.user.display_name,
                    "reason": self.reason,
                    "rel": self.expected_release or _("unspecified"),
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        else:  # release
            if not partner.is_credit_held:
                raise UserError(_("This partner is not on hold."))
            partner.sudo().write({
                "is_credit_held": False,
                "credit_hold_reason": False,
                "credit_hold_applied_at": False,
                "credit_hold_applied_by": False,
                "credit_hold_expected_release": False,
            })
            Log.create({
                "partner_id": partner.id,
                "event": "hold_released",
                "reason": self.reason,
                "by_user_id": self.env.user.id,
            })
            partner.message_post(
                body=_(
                    "<b>Credit hold released</b> by %(by)s.<br/>Reason: %(reason)s"
                ) % {"by": self.env.user.display_name, "reason": self.reason},
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Credit hold updated"),
                "message": (
                    _("%s is now on hold.") % partner.display_name
                    if self.mode == "hold"
                    else _("%s released from hold.") % partner.display_name
                ),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
