from odoo import fields, models


class CmSaCreditHoldLog(models.Model):
    _name = "cm_sa.credit_hold.log"
    _description = "Credit Hold Log"
    _order = "at desc, id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event = fields.Selection(
        [
            ("hold_applied", "Hold Applied"),
            ("hold_released", "Hold Released"),
            ("block_triggered", "Block Triggered"),
        ],
        required=True,
        index=True,
    )
    reason = fields.Text()
    by_user_id = fields.Many2one(
        "res.users",
        string="By User",
        default=lambda self: self.env.user.id,
    )
    at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    ref_model = fields.Char(string="Blocked Model")
    ref_id = fields.Integer(string="Blocked Record ID")
    ref_ref = fields.Reference(
        selection="_reference_models",
        compute="_compute_ref_ref",
        string="Blocked Record",
    )

    def _reference_models(self):
        return [(m.model, m.name) for m in self.env["ir.model"].sudo().search([])]

    def _compute_ref_ref(self):
        for rec in self:
            rec.ref_ref = (
                "%s,%s" % (rec.ref_model, rec.ref_id)
                if rec.ref_model and rec.ref_id
                else False
            )
