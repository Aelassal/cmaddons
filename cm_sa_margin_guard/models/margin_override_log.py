from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError

from .margin_guard_rule import CTX_AUDIT_CREATE

CTX_AUDIT_MAINTENANCE = "cm_sa_margin_guard_audit_maintenance"


class CmSaMarginOverrideLog(models.Model):
    _name = "cm_sa.margin.override.log"
    _description = "Margin Guard Override Log"
    _order = "create_date desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.margin.guard.rule",
        string="Rule",
        ondelete="restrict",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_name = fields.Char()
    user_id = fields.Many2one(
        "res.users",
        string="Overridden By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    threshold_pct = fields.Float(string="Threshold %")
    actual_pct = fields.Float(string="Actual Margin %")
    gap_pct = fields.Float(
        string="Gap",
        compute="_compute_gap_pct",
        store=True,
    )
    reason = fields.Text()

    @api.depends("threshold_pct", "actual_pct")
    def _compute_gap_pct(self):
        for rec in self:
            rec.gap_pct = (rec.threshold_pct or 0.0) - (rec.actual_pct or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(CTX_AUDIT_CREATE):
            raise AccessError(
                _(
                    "Margin Override Log entries are created automatically "
                    "by Margin Guard and cannot be created manually."
                )
            )
        return super().create(vals_list)

    def _allow_audit_maintenance(self):
        return (
            self.env.uid == SUPERUSER_ID
            and self.env.context.get(CTX_AUDIT_MAINTENANCE)
        )

    def write(self, vals):
        if not self._allow_audit_maintenance():
            raise AccessError(
                _(
                    "Margin Override Log is an immutable audit trail. "
                    "Existing entries cannot be modified."
                )
            )
        return super().write(vals)

    def unlink(self):
        if not self._allow_audit_maintenance():
            raise AccessError(
                _(
                    "Margin Override Log is a permanent audit trail. "
                    "Existing entries cannot be deleted."
                )
            )
        return super().unlink()

    def action_open_source(self):
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env.registry:
            raise AccessError(_("The source model is no longer available."))
        source = self.env[self.res_model].browse(self.res_id).exists()
        if not source:
            raise AccessError(_("The source record no longer exists."))
        source.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
