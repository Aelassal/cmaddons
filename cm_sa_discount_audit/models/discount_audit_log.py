from odoo import fields, models


class CmSaDiscountAuditLog(models.Model):
    _name = "cm_sa.discount.audit.log"
    _description = "Discount Audit Log"
    _order = "create_date desc, id desc"

    order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    order_line_id = fields.Many2one(
        "sale.order.line",
        string="Order Line",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        related="order_id.partner_id", store=True, readonly=True, index=True,
    )
    salesperson_id = fields.Many2one(
        related="order_id.user_id", store=True, readonly=True, index=True,
        string="Salesperson",
    )
    team_id = fields.Many2one(
        related="order_id.team_id", store=True, readonly=True,
    )
    product_id = fields.Many2one(
        related="order_line_id.product_id", store=True, readonly=True, index=True,
    )
    discount_pct = fields.Float(string="Discount %", required=True)
    threshold_pct = fields.Float(string="Threshold %")
    list_price = fields.Float(string="List Price")
    unit_price = fields.Float(string="Unit Price")
    qty = fields.Float(string="Quantity")
    discount_amount = fields.Float(
        string="Discount Amount",
        compute="_compute_discount_amount",
        store=True,
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id", store=True, readonly=True,
    )
    reason = fields.Text()

    def _compute_discount_amount(self):
        for rec in self:
            rec.discount_amount = (
                (rec.list_price - rec.unit_price) * (rec.qty or 0.0)
            )

    def action_open_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
            "target": "current",
        }
