from odoo import _, fields, models


class CmSaScanNowWizard(models.TransientModel):
    _name = "cm_sa.negative.stock.scan_now.wizard"
    _description = "Scan Negative Stock Now"

    config_id = fields.Many2one(
        "cm_sa.negative.stock.config",
        string="Configuration",
        required=True,
        default=lambda self: self.env["cm_sa.negative.stock.config"]
            .sudo().get_singleton(),
    )

    def action_run(self):
        self.ensure_one()
        return self.config_id.action_scan_now()
