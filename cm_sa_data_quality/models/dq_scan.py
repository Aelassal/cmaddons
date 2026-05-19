from odoo import fields, models


class CmSaDqScan(models.Model):
    _name = "cm_sa.dq.scan"
    _description = "Data Quality Scan"
    _order = "started_at desc, id desc"

    started_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    completed_at = fields.Datetime(readonly=True)
    rules_run = fields.Integer(readonly=True)
    records_scanned = fields.Integer(readonly=True)
    findings_info = fields.Integer(readonly=True)
    findings_warn = fields.Integer(readonly=True)
    findings_fail = fields.Integer(readonly=True)
    triggered_by = fields.Many2one(
        "res.users",
        string="Triggered By",
        default=lambda self: self.env.user.id,
        readonly=True,
    )
    duration_seconds = fields.Float(readonly=True)
    notes = fields.Char(readonly=True)
