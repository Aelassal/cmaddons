import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CmSaReasonRule(models.Model):
    _name = "cm_sa.reason.rule"
    _description = "Field Change Reason Rule"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        index=True,
    )
    field_ids = fields.Many2many(
        "ir.model.fields",
        "cm_sa_reason_rule_field_rel",
        "rule_id",
        "field_id",
        string="Guarded Fields",
        required=True,
        domain="[('model_id', '=', model_id), ('readonly', '=', False)]",
    )
    reason_category_ids = fields.Many2many(
        "cm_sa.reason.category",
        "cm_sa_reason_rule_cat_rel",
        "rule_id",
        "category_id",
        string="Allowed Categories",
        required=True,
    )
    require_note = fields.Boolean(default=True)
    min_note_chars = fields.Integer(default=10)

    binding_action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Cog-menu Binding",
        readonly=True,
        ondelete="set null",
        help="Contextual action installed on the target model. Recreated when "
             "the rule is saved or the model changes.",
    )

    @api.constrains("min_note_chars", "require_note")
    def _check_min_note_chars(self):
        for rec in self:
            if rec.require_note and rec.min_note_chars < 0:
                raise ValidationError(_("Minimum note length must be >= 0."))

    # ------------------------------------------------------------------
    # CRUD: keep the contextual binding action in sync with the rule
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._sync_binding_action()
        return records

    def write(self, vals):
        res = super().write(vals)
        # If model changed, re-point the binding action at the new model
        if "model_id" in vals or "name" in vals or "active" in vals:
            for rec in self:
                rec._sync_binding_action()
        return res

    def unlink(self):
        for rec in self:
            if rec.binding_action_id:
                try:
                    rec.binding_action_id.unlink()
                except Exception:
                    pass
        return super().unlink()

    def _sync_binding_action(self):
        """(Re-)create the cog-menu act_window so this rule is launchable
        from any record list/form on the target model."""
        self.ensure_one()
        if not self.model_id or not self.model_name:
            return
        Wizard = self.env["ir.model"].sudo().search(
            [("model", "=", "cm_sa.reason.wizard")], limit=1,
        )
        if not Wizard:
            return
        vals = {
            "name": _("Change with Reason — %s") % self.name,
            "res_model": "cm_sa.reason.wizard",
            "binding_model_id": self.model_id.id,
            "binding_view_types": "form,list",
            "view_mode": "form",
            "target": "new",
            "context": "{'default_rule_id': %s, 'default_res_model': '%s'}" % (
                self.id, self.model_name,
            ),
        }
        if self.binding_action_id:
            try:
                self.binding_action_id.sudo().write(vals)
                if not self.active:
                    self.binding_action_id.sudo().write({
                        "binding_model_id": False,
                    })
                return
            except Exception:
                _logger.warning("reason_guard: could not update binding action")
        try:
            action = self.env["ir.actions.act_window"].sudo().create(vals)
            self.binding_action_id = action.id
        except Exception as exc:
            _logger.warning("reason_guard: failed to create binding: %s", exc)
