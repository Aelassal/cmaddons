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
        string="Requiring Override",
    )
    violation_summary = fields.Text(readonly=True)
    processed_summary = fields.Text(readonly=True)
    blocked_summary = fields.Text(readonly=True)
    min_length = fields.Integer(readonly=True, default=10)
    reason = fields.Text(required=True)

    @api.depends("record_id_str", "model_name")
    def _compute_records_preview(self):
        for rec in self:
            if not rec.record_id_str or not rec.model_name:
                rec.records_preview = ""
                continue
            try:
                ids = [int(item) for item in rec.record_id_str.split(",") if item]
                records = self.env[rec.model_name].browse(ids).exists()
                names = records.mapped("display_name")[:10]
                extra = len(records) - len(names)
                preview = ", ".join(names)
                if extra > 0:
                    preview += _(" ... (+%s more)") % extra
                rec.records_preview = preview
            except Exception:
                rec.records_preview = rec.record_id_str

    def action_confirm_override(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if self.min_length and len(reason) < self.min_length:
            raise UserError(
                _("Reason must be at least %d characters long.")
                % self.min_length
            )

        if not self.model_name or self.model_name not in self.env.registry:
            raise UserError(
                _("Target model %s is no longer available.") % self.model_name
            )
        ids = [
            int(item)
            for item in (self.record_id_str or "").split(",")
            if item
        ]
        records = self.env[self.model_name].browse(ids).exists()
        if not records:
            raise UserError(_("The selected records no longer exist."))

        method = getattr(records, self.method_name, None)
        if not callable(method):
            raise UserError(
                _("Model %(model)s has no method %(method)s.")
                % {"model": self.model_name, "method": self.method_name}
            )

        result = getattr(
            records.with_context(**{CTX_REASON: reason}), self.method_name
        )()
        if isinstance(result, dict):
            return result
        return {"type": "ir.actions.act_window_close"}
