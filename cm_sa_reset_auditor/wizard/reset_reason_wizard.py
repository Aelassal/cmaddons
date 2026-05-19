from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.reset_audit_rule import CTX_REASON


class CmSaResetAuditWizard(models.TransientModel):
    _name = "cm_sa.reset_audit.wizard"
    _description = "Reset-to-Draft Reason Wizard"

    rule_id = fields.Many2one(
        "cm_sa.reset_audit.rule",
        string="Rule",
        readonly=True,
    )
    model_name = fields.Char(required=True, readonly=True)
    method_name = fields.Char(required=True, readonly=True)
    # Records being reset — stored as comma-separated ids so we can re-browse
    # them on the real model when the user confirms.
    record_id_str = fields.Char(required=True, readonly=True)
    records_preview = fields.Char(
        compute="_compute_records_preview",
        string="Resetting",
    )
    reason = fields.Text(required=True)
    min_length = fields.Integer(readonly=True, default=10)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        # Translate the default_record_ids Many2many command into a
        # comma-separated id list so we can re-browse on the real model.
        ctx = self.env.context
        ids = []
        rec_cmd = ctx.get("default_record_ids")
        if rec_cmd:
            for cmd in rec_cmd:
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
                    if cmd[0] == 6:
                        ids = list(cmd[2] or [])
        vals["record_id_str"] = ",".join(str(i) for i in ids)
        return vals

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

    def action_confirm_reset(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if self.min_length and len(reason) < self.min_length:
            raise UserError(_(
                "Reason must be at least %d characters long."
            ) % self.min_length)
        if not reason:
            raise UserError(_("Reason is required."))

        if not self.model_name or self.model_name not in self.env:
            raise UserError(_("Target model %s is no longer available.") % self.model_name)
        ids = [int(x) for x in (self.record_id_str or "").split(",") if x]
        if not ids:
            raise UserError(_("No records selected to reset."))
        records = self.env[self.model_name].browse(ids).exists()
        if not records:
            raise UserError(_(
                "The selected records no longer exist."
            ))

        method = getattr(records, self.method_name, None)
        if not callable(method):
            raise UserError(_(
                "Model %(model)s has no method %(method)s."
            ) % {"model": self.model_name, "method": self.method_name})

        # Invoke the wrapper with the reason in context so the wrapper skips
        # the "reason required" check and logs this reason.
        getattr(records.with_context(**{CTX_REASON: reason}), self.method_name)()
        return {"type": "ir.actions.act_window_close"}
