from odoo import fields, models


class CmSaFilestoreSweepRun(models.Model):
    _name = "cm_sa.filestore.sweep.run"
    _description = "Filestore Sweep Run"
    _order = "started_at desc, id desc"
    _rec_name = "started_at"

    started_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    completed_at = fields.Datetime(readonly=True)
    total_scanned = fields.Integer(readonly=True)
    orphan_count = fields.Integer(readonly=True)
    orphan_size_mb = fields.Float(readonly=True, digits=(12, 3))
    deleted_count = fields.Integer(readonly=True)
    deleted_size_mb = fields.Float(readonly=True, digits=(12, 3))
    triggered_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user.id,
        readonly=True,
    )
    dry_run = fields.Boolean(readonly=True)
    notes = fields.Text(readonly=True)
