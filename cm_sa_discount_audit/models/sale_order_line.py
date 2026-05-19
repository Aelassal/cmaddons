import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cm_sa_discount_reason = fields.Char(
        string="Discount Reason",
        help="Optional free-text reason for a non-standard discount. Copied "
             "onto the audit-log row when the discount exceeds the "
             "configured threshold.",
    )

    def _cm_sa_audit_discount(self, previous_discounts=None):
        """Write audit-log rows for lines that exceed the current threshold.

        ``previous_discounts`` (optional) maps line_id → prior discount %.
        We only emit a row when a line crosses the threshold on this
        create/write, not on every save. Missing key = treated as 0.
        """
        Config = self.env["cm_sa.discount.audit.config"].sudo()
        try:
            config = Config.get_singleton()
        except Exception:
            _logger.exception("DiscountAudit: could not load config; skipping.")
            return
        threshold = config.threshold_pct or 0.0
        Log = self.env["cm_sa.discount.audit.log"].sudo()

        for line in self:
            current = line.discount or 0.0
            prior = (previous_discounts or {}).get(line.id, 0.0)
            # Audit when current crosses above threshold, OR when an existing
            # above-threshold discount is modified upward.
            if current <= threshold:
                continue
            if prior > threshold and current <= prior:
                # Already audited before and didn't get worse — don't spam.
                continue

            list_price = getattr(line, "price_unit", 0.0) and (
                line.price_unit / (1 - current / 100.0)
                if current < 100 else line.price_unit
            )
            try:
                Log.create({
                    "order_id": line.order_id.id,
                    "order_line_id": line.id,
                    "discount_pct": current,
                    "threshold_pct": threshold,
                    "list_price": list_price,
                    "unit_price": line.price_unit or 0.0,
                    "qty": line.product_uom_qty or 0.0,
                    "reason": line.cm_sa_discount_reason or "",
                })
            except Exception:
                _logger.exception(
                    "DiscountAudit: failed to write log for line %s", line.id,
                )
                continue

            if config.post_chatter_on_audit and line.order_id:
                try:
                    line.order_id.message_post(
                        body=_(
                            "Discount Audit: line <b>%(prod)s</b> "
                            "discounted <b>%(disc).1f%%</b> (above "
                            "%(thr).1f%% threshold). Reason: %(reason)s"
                        ) % {
                            "prod": line.product_id.display_name or
                                (line.name or "")[:60],
                            "disc": current,
                            "thr": threshold,
                            "reason": line.cm_sa_discount_reason or _("(none)"),
                        },
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            records._cm_sa_audit_discount()
        except Exception:
            _logger.exception("DiscountAudit: create-time audit failed.")
        return records

    def write(self, vals):
        # Capture prior discount values before the write applies.
        prior = {l.id: (l.discount or 0.0) for l in self}
        res = super().write(vals)
        if "discount" in vals:
            try:
                self._cm_sa_audit_discount(previous_discounts=prior)
            except Exception:
                _logger.exception("DiscountAudit: write-time audit failed.")
        return res
