from odoo import fields, models


class CmSaJanitorLog(models.Model):
    _name = "cm_sa.janitor.log"
    _description = "Draft Document Janitor Log"
    _order = "executed_at desc, id desc"
    _rec_name = "record_name"

    rule_id = fields.Many2one(
        "cm_sa.janitor.rule",
        string="Rule",
        ondelete="set null",
        index=True,
    )
    record_ref = fields.Reference(
        selection="_reference_models",
        string="Record",
    )
    model_name = fields.Char(string="Model", index=True)
    record_name = fields.Char(string="Record Name")
    action_taken = fields.Selection(
        [
            ("notify_owner", "Notified Owner"),
            ("auto_cancel", "Auto-cancelled"),
            ("auto_archive", "Auto-archived"),
            ("error", "Error"),
        ],
        string="Action Taken",
    )
    error_message = fields.Text()
    executed_at = fields.Datetime(default=fields.Datetime.now, index=True)

    def _reference_models(self):
        return [(m.model, m.name) for m in self.env["ir.model"].sudo().search([])]
