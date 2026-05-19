from odoo import _, api, fields, models


class CmSaNegativeStockSnapshot(models.Model):
    _name = "cm_sa.negative.stock.snapshot"
    _description = "Negative Stock Snapshot"
    _order = "scan_date desc, id desc"
    _rec_name = "display_name"

    config_id = fields.Many2one(
        "cm_sa.negative.stock.config",
        ondelete="cascade",
        required=True,
    )
    scan_date = fields.Date(required=True, default=fields.Date.context_today)
    triggered_by = fields.Selection(
        [("cron", "Cron"), ("manual", "Manual")],
        default="cron",
        required=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)
    line_ids = fields.One2many(
        "cm_sa.negative.stock.line", "snapshot_id",
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)
    location_count = fields.Integer(compute="_compute_totals", store=True)
    total_quantity = fields.Float(
        compute="_compute_totals", store=True, digits=(16, 3),
    )
    max_aging_days = fields.Integer(compute="_compute_totals", store=True)

    @api.depends("scan_date", "triggered_by")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("%(date)s — %(trig)s") % {
                "date": rec.scan_date or "", "trig": rec.triggered_by or "",
            }

    @api.depends("line_ids", "line_ids.quantity", "line_ids.aging_days",
                 "line_ids.location_id")
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.location_count = len(lines.mapped("location_id"))
            rec.total_quantity = sum(lines.mapped("quantity"))
            rec.max_aging_days = max(lines.mapped("aging_days") or [0])


class CmSaNegativeStockLine(models.Model):
    _name = "cm_sa.negative.stock.line"
    _description = "Negative Stock Line"
    _order = "aging_days desc, quantity asc"

    snapshot_id = fields.Many2one(
        "cm_sa.negative.stock.snapshot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", index=True,
    )
    location_id = fields.Many2one(
        "stock.location", required=True, ondelete="restrict", index=True,
    )
    quantity = fields.Float(digits=(16, 3))
    aging_days = fields.Integer()
    write_date_first = fields.Date(
        string="First Seen At",
        help="write_date on the stock.quant — earliest time this negative "
             "quantity was last touched.",
    )

    def action_open_quant(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "domain": [
                ("product_id", "=", self.product_id.id),
                ("location_id", "=", self.location_id.id),
            ],
        }
