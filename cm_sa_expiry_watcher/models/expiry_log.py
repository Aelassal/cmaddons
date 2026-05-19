from odoo import fields, models


class CmSaExpiryLog(models.Model):
    _name = "cm_sa.expiry.log"
    _description = "Expiry Watcher Log"
    _order = "triggered_at desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.expiry.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(string="Model", required=True, index=True)
    res_id = fields.Integer(string="Record ID", required=True, index=True)
    res_ref = fields.Reference(
        selection="_reference_models",
        compute="_compute_res_ref",
        string="Record",
    )
    record_name = fields.Char(string="Record Name")
    expiry_date = fields.Date(required=True, index=True)
    days_remaining = fields.Integer()
    notified_user_ids = fields.Many2many(
        "res.users",
        "cm_sa_expiry_log_user_rel",
        "log_id",
        "user_id",
        string="Notified Users",
    )
    email_sent = fields.Boolean()
    triggered_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )

    _expiry_log_uniq = models.Constraint(
        "unique(rule_id, res_model, res_id, expiry_date)",
        "An alert for this rule + record + expiry date already exists.",
    )

    def _reference_models(self):
        return [(m.model, m.name) for m in self.env["ir.model"].sudo().search([])]

    def _compute_res_ref(self):
        for rec in self:
            rec.res_ref = (
                "%s,%s" % (rec.res_model, rec.res_id)
                if rec.res_model and rec.res_id
                else False
            )
