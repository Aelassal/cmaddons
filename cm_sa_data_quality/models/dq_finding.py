from odoo import _, fields, models


class CmSaDqFinding(models.Model):
    _name = "cm_sa.dq.finding"
    _description = "Data Quality Finding"
    _order = "last_seen desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.dq.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(string="Model", required=True, index=True)
    res_id = fields.Integer(string="Record ID", required=True, index=True)
    record_name = fields.Char(string="Record Name")
    first_seen = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    last_seen = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    severity = fields.Selection(
        [("info", "Info"), ("warn", "Warn"), ("fail", "Fail")],
        required=True,
        default="warn",
        index=True,
    )
    resolved = fields.Boolean(default=False, index=True)
    resolved_at = fields.Datetime(readonly=True)
    detail = fields.Char(help="Short description of what failed, e.g. the offending value.")

    res_ref = fields.Reference(
        selection="_reference_models",
        compute="_compute_res_ref",
        string="Record",
    )

    _finding_uniq = models.Constraint(
        "unique(rule_id, res_model, res_id)",
        "A finding for this rule + record already exists.",
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

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def action_mark_resolved(self):
        for rec in self:
            rec.write({
                "resolved": True,
                "resolved_at": fields.Datetime.now(),
            })
        return True
