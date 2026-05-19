from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.attachment_rule import CTX_REASON


class CmSaAttachmentBypassWizard(models.TransientModel):
    _name = "cm_sa.attachment.bypass.wizard"
    _description = "Attachment Enforcer Bypass Wizard"

    rule_id = fields.Many2one("cm_sa.attachment.rule", readonly=True)
    move_id_str = fields.Char(required=True, readonly=True)
    moves_preview = fields.Char(
        compute="_compute_moves_preview", string="Moves",
    )
    min_length = fields.Integer(readonly=True, default=10)
    reason = fields.Text(required=True)

    @api.depends("move_id_str")
    def _compute_moves_preview(self):
        for rec in self:
            if not rec.move_id_str:
                rec.moves_preview = ""
                continue
            try:
                ids = [int(x) for x in rec.move_id_str.split(",") if x]
                moves = self.env["account.move"].browse(ids).exists()
                names = moves.mapped("display_name")[:5]
                extra = len(moves) - len(names)
                preview = ", ".join(names)
                if extra > 0:
                    preview += _(" … (+%s more)") % extra
                rec.moves_preview = preview
            except Exception:
                rec.moves_preview = rec.move_id_str

    def action_confirm_bypass(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if self.min_length and len(reason) < self.min_length:
            raise UserError(_(
                "Bypass reason must be at least %d characters long."
            ) % self.min_length)
        if not reason:
            raise UserError(_("Reason is required."))

        ids = [int(x) for x in (self.move_id_str or "").split(",") if x]
        moves = self.env["account.move"].browse(ids).exists()
        if not moves:
            raise UserError(_("The selected move(s) no longer exist."))
        # Re-invoke the wrapped method with the reason in context.
        moves.with_context(**{CTX_REASON: reason}).action_post()
        return {"type": "ir.actions.act_window_close"}
