from odoo import fields, models


class CmSaReturnReasonLog(models.Model):
    _name = "cm_sa.return.reason.log"
    _description = "Return Reason Log"
    _order = "create_date desc, id desc"

    source_picking_id = fields.Many2one(
        "stock.picking",
        string="Source Picking",
        ondelete="set null",
        index=True,
    )
    return_picking_id = fields.Many2one(
        "stock.picking",
        string="Return Picking",
        ondelete="set null",
    )
    partner_id = fields.Many2one(
        related="source_picking_id.partner_id", store=True, readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Created By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    category_id = fields.Many2one(
        "cm_sa.return.reason.category",
        string="Reason Category",
        ondelete="set null",
    )
    reason = fields.Text(required=True)
    line_ids = fields.One2many(
        "cm_sa.return.reason.log.line", "log_id",
    )

    def action_open_source(self):
        self.ensure_one()
        if not self.source_picking_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.source_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_return(self):
        self.ensure_one()
        if not self.return_picking_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.return_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }


class CmSaReturnReasonLogLine(models.Model):
    """Per-product breakdown — enables pivot by reason × product."""

    _name = "cm_sa.return.reason.log.line"
    _description = "Return Reason Log Line"

    log_id = fields.Many2one(
        "cm_sa.return.reason.log", required=True, ondelete="cascade", index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", index=True,
    )
    qty = fields.Float(digits=(16, 3))
    category_id = fields.Many2one(
        related="log_id.category_id", store=True, readonly=True, index=True,
    )
    partner_id = fields.Many2one(
        related="log_id.partner_id", store=True, readonly=True, index=True,
    )
    reason = fields.Text(related="log_id.reason", store=False, readonly=True)
    log_create_date = fields.Datetime(
        related="log_id.create_date", store=True, readonly=True, index=True,
    )
