from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.margin_guard_rule import CTX_REASON


class CmSaMarginOverrideWizard(models.TransientModel):
    _name = "cm_sa.margin.override.wizard"
    _description = "Margin Override Reason Wizard"

    rule_id = fields.Many2one(
        "cm_sa.margin.guard.rule",
        readonly=True,
    )
    model_name = fields.Char(required=True, readonly=True)
    method_name = fields.Char(required=True, readonly=True)
    record_id_str = fields.Char(required=True, readonly=True)
    records_preview = fields.Char(
        compute="_compute_records_preview",
        string="Confirming",
    )
    actual_margin = fields.Float(
        string="Actual Margin %",
        readonly=True,
    )
    threshold = fields.Float(
        string="Threshold %",
        readonly=True,
    )
    min_length = fields.Integer(readonly=True, default=10)
    reason = fields.Text(required=True)

    @api.depends("record_id_str", "model_name")
    def _compute_records_preview(self):
        for rec in self:
            if not rec.record_id_str or not rec.model_name:
                rec.records_preview = ""
                continue
            try:
                ids = [int(x) for x in rec.record_id_str.split(",") if x]
                Model = self.env[rec.model_name]
                records = Model.browse(ids).exists()
                names = records.mapped("display_name")[:5]
                extra = len(records) - len(names)
                preview = ", ".join(names)
                if extra > 0:
                    preview += _(" … (+%s more)") % extra
                rec.records_preview = preview
            except Exception:
                rec.records_preview = rec.record_id_str

    def action_confirm_override(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if self.min_length and len(reason) < self.min_length:
            raise UserError(_(
                "Reason must be at least %d characters long."
            ) % self.min_length)

        if not self.model_name or self.model_name not in self.env:
            raise UserError(_("Target model %s is no longer available.") % self.model_name)
        ids = [int(x) for x in (self.record_id_str or "").split(",") if x]
        records = self.env[self.model_name].browse(ids).exists()
        if not records:
            raise UserError(_("The selected records no longer exist."))

        method = getattr(records, self.method_name, None)
        if not callable(method):
            raise UserError(_(
                "Model %(model)s has no method %(method)s."
            ) % {"model": self.model_name, "method": self.method_name})

        # Re-invoke the wrapped method with the reason in context so the
        # wrapper skips the wizard branch.
        getattr(records.with_context(**{CTX_REASON: reason}), self.method_name)()
        return {"type": "ir.actions.act_window_close"}
