from odoo import fields, models


class CmSaTransferSlaLog(models.Model):
    _name = "cm_sa.transfer.sla.log"
    _description = "Transfer SLA Alert Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.transfer.sla.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Picking",
        ondelete="cascade",
        index=True,
    )
    picking_name = fields.Char(
        related="picking_id.name", store=True, readonly=True,
    )
    picking_type_id = fields.Many2one(
        related="picking_id.picking_type_id", store=True, readonly=True,
    )
    location_id = fields.Many2one(
        related="picking_id.location_id", store=True, readonly=True,
    )
    location_dest_id = fields.Many2one(
        related="picking_id.location_dest_id", store=True, readonly=True,
    )
    days_overdue = fields.Integer(index=True)
    bucket_key = fields.Integer(
        string="Escalation Bucket",
        help="0 = initial threshold, N = Nth escalation bucket.",
    )
    scheduled_date = fields.Datetime(
        string="Scheduled Date (at alert)",
    )

    def action_open_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.picking_id.id,
            "view_mode": "form",
            "target": "current",
        }
