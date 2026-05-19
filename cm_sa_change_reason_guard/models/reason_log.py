from odoo import fields, models


class CmSaReasonLog(models.Model):
    _name = "cm_sa.reason.log"
    _description = "Field Change Reason Log"
    _order = "changed_at desc, id desc"
    _rec_name = "id"

    rule_id = fields.Many2one(
        "cm_sa.reason.rule",
        string="Rule",
        ondelete="set null",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    res_ref = fields.Reference(
        selection="_reference_models",
        compute="_compute_res_ref",
        string="Record",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Changed By",
        default=lambda self: self.env.user.id,
        required=True,
    )
    changed_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    changed_field_names = fields.Text()
    category_id = fields.Many2one(
        "cm_sa.reason.category",
        string="Category",
    )
    note = fields.Text()
    old_values_json = fields.Text()
    new_values_json = fields.Text()

    def _reference_models(self):
        return [(m.model, m.name) for m in self.env["ir.model"].sudo().search([])]

    def _compute_res_ref(self):
        for rec in self:
            rec.res_ref = (
                "%s,%s" % (rec.res_model, rec.res_id)
                if rec.res_model and rec.res_id
                else False
            )
