import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vendor_perf_score = fields.Integer(
        string="Vendor Score",
        readonly=True,
        copy=False,
        index=True,
    )
    vendor_perf_band = fields.Selection(
        [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        string="Vendor Band",
        readonly=True,
        copy=False,
        index=True,
    )
    vendor_perf_updated_at = fields.Datetime(
        string="Vendor Score Updated At",
        readonly=True,
        copy=False,
    )
    vendor_perf_breakdown_json = fields.Text(
        string="Vendor Score Breakdown (JSON)",
        readonly=True,
        copy=False,
    )

    vendor_perf_snapshot_ids = fields.One2many(
        "cm_sa.vendor_scorecard.snapshot",
        "vendor_id",
        string="Scorecard History",
        readonly=True,
    )
    vendor_perf_snapshot_count = fields.Integer(
        compute="_compute_vendor_perf_snapshot_count",
    )

    @api.depends("vendor_perf_snapshot_ids")
    def _compute_vendor_perf_snapshot_count(self):
        for rec in self:
            rec.vendor_perf_snapshot_count = len(rec.vendor_perf_snapshot_ids)

    def action_view_vendor_perf_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor Scorecard History"),
            "res_model": "cm_sa.vendor_scorecard.snapshot",
            "view_mode": "list,form",
            "domain": [("vendor_id", "=", self.id)],
        }

    def action_compute_vendor_score(self):
        config = self.env["cm_sa.vendor_scorecard.config"].sudo()._get_active()
        if not config:
            return
        for rec in self:
            rec._compute_and_store_vendor_score(config)
        return True

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    def _vendor_metric_on_time(self, window_start, window_end):
        """Return (on_time_pct, avg_days_late, sample) over window."""
        self.ensure_one()
        Pick = self.env["stock.picking"].sudo()
        pickings = Pick.search([
            ("partner_id", "=", self.id),
            ("picking_type_code", "=", "incoming"),
            ("state", "=", "done"),
            ("date_done", ">=", fields.Datetime.to_string(
                datetime.combine(window_start, datetime.min.time())
            )),
            ("date_done", "<=", fields.Datetime.to_string(
                datetime.combine(window_end, datetime.max.time())
            )),
        ])
        if not pickings:
            return (None, 0.0, 0)
        on_time = 0
        late_days_total = 0.0
        late_cnt = 0
        for p in pickings:
            planned = p.scheduled_date or p.date_deadline
            done = p.date_done
            if not planned or not done:
                continue
            planned_dt = planned if isinstance(planned, datetime) else datetime.combine(
                planned, datetime.min.time()
            )
            done_dt = done if isinstance(done, datetime) else datetime.combine(
                done, datetime.min.time()
            )
            delta = (done_dt - planned_dt).total_seconds() / 86400.0
            if delta <= 0:
                on_time += 1
            else:
                late_days_total += delta
                late_cnt += 1
        total = len(pickings)
        pct = 100.0 * on_time / total if total else 0.0
        avg_late = (late_days_total / late_cnt) if late_cnt else 0.0
        return (pct, avg_late, total)

    def _vendor_metric_price_variance(self, window_start, window_end, ref_days):
        """Return variance % across (vendor, product) pairs."""
        self.ensure_one()
        Line = self.env["purchase.order.line"].sudo()
        try:
            recent = Line.search([
                ("partner_id", "=", self.id),
                ("state", "in", ("purchase", "done")),
                ("date_order", ">=", fields.Datetime.to_string(
                    datetime.combine(window_start, datetime.min.time())
                )),
                ("date_order", "<=", fields.Datetime.to_string(
                    datetime.combine(window_end, datetime.max.time())
                )),
                ("product_id", "!=", False),
            ])
        except Exception:
            # Fall back to a lighter query if date_order not searchable
            recent = self.env["purchase.order.line"]
        if not recent:
            return (None, 0)
        ref_start = window_end - timedelta(days=ref_days)
        ref_lines = Line.search([
            ("partner_id", "=", self.id),
            ("state", "in", ("purchase", "done")),
            ("date_order", ">=", fields.Datetime.to_string(
                datetime.combine(ref_start, datetime.min.time())
            )),
            ("date_order", "<", fields.Datetime.to_string(
                datetime.combine(window_end, datetime.max.time())
            )),
            ("product_id", "!=", False),
        ])
        # Baseline avg price per product across ref window
        baseline = defaultdict(list)
        for l in ref_lines:
            if l.price_unit:
                baseline[l.product_id.id].append(float(l.price_unit))
        variances = []
        latest_by_product = {}
        for l in recent.sorted(lambda r: r.date_order or fields.Datetime.now()):
            if l.price_unit:
                latest_by_product[l.product_id.id] = float(l.price_unit)
        for product_id, latest_price in latest_by_product.items():
            baseline_prices = baseline.get(product_id) or []
            if not baseline_prices:
                continue
            baseline_avg = sum(baseline_prices) / len(baseline_prices)
            if baseline_avg <= 0:
                continue
            variance = abs(latest_price - baseline_avg) / baseline_avg
            variances.append(variance)
        if not variances:
            return (None, 0)
        avg_variance = sum(variances) / len(variances)
        return (avg_variance * 100.0, len(variances))

    def _vendor_metric_bill_disputes(self, window_start, window_end):
        """Count vendor bills reset to draft after post, or cancelled after post,
        within window. We approximate via ``mail.message`` tracking.
        """
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        bills = Move.search([
            ("partner_id", "=", self.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("invoice_date", ">=", fields.Date.to_string(window_start)),
            ("invoice_date", "<=", fields.Date.to_string(window_end)),
        ])
        if not bills:
            return (0, 0)
        dispute = 0
        for b in bills:
            # state now is draft but was posted at some point: treat as dispute
            try:
                if b.state == "draft":
                    # Look through messages for posted->draft transitions
                    msgs = self.env["mail.message"].sudo().search_count([
                        ("model", "=", "account.move"),
                        ("res_id", "=", b.id),
                        ("subtype_id", "=", False),
                    ])
                    if msgs:
                        dispute += 1
                elif b.state == "cancel":
                    dispute += 1
            except Exception:
                continue
        return (dispute, len(bills))

    def _compute_and_store_vendor_score(self, config):
        self.ensure_one()
        today = fields.Date.context_today(self)
        window_start = today - timedelta(days=config.window_days)
        window_end = today

        on_time_pct, avg_days_late, receipt_n = self._vendor_metric_on_time(
            window_start, window_end,
        )
        var_pct, var_n = self._vendor_metric_price_variance(
            window_start, window_end, config.price_reference_days,
        )
        dispute_n, bill_n = self._vendor_metric_bill_disputes(
            window_start, window_end,
        )

        # Convert each metric to 0..100 points
        # On-time: 100% -> 100 pts, 50% -> 0 pts, linear
        on_time_pts = None
        if on_time_pct is not None:
            on_time_pts = max(0.0, min(100.0, (on_time_pct - 50.0) * 2.0))
        # Price variance: 0% -> 100 pts, 20%+ -> 0 pts, linear
        var_pts = None
        if var_pct is not None:
            var_pts = max(0.0, min(100.0, 100.0 * (1.0 - var_pct / 20.0)))
        # Bill disputes: 0/bills -> 100 pts, 30%+ -> 0 pts, linear
        dispute_pts = None
        if bill_n:
            ratio = dispute_n / bill_n
            dispute_pts = max(0.0, min(100.0, 100.0 * (1.0 - ratio / 0.3)))

        comps = [
            (on_time_pts, config.weight_on_time),
            (var_pts, config.weight_price_variance),
            (dispute_pts, config.weight_bill_dispute),
        ]
        num = 0.0
        den = 0.0
        for pts, w in comps:
            if pts is None or w <= 0:
                continue
            num += pts * w
            den += w
        score = int(round(num / den)) if den > 0 else 0
        score = max(0, min(100, score))
        band = config.band_for_score(score)

        breakdown = {
            "window_days": config.window_days,
            "on_time_pct": round(on_time_pct, 2) if on_time_pct is not None else None,
            "avg_days_late": round(avg_days_late, 2),
            "price_variance_pct": round(var_pct, 2) if var_pct is not None else None,
            "price_variance_samples": var_n,
            "bill_dispute_count": dispute_n,
            "bill_total": bill_n,
            "receipt_count": receipt_n,
            "metric_points": {
                "on_time": on_time_pts,
                "price_variance": var_pts,
                "bill_dispute": dispute_pts,
            },
            "weights": {
                "on_time": config.weight_on_time,
                "price_variance": config.weight_price_variance,
                "bill_dispute": config.weight_bill_dispute,
            },
            "score": score,
            "band": band,
        }

        self.sudo().write({
            "vendor_perf_score": score,
            "vendor_perf_band": band,
            "vendor_perf_updated_at": fields.Datetime.now(),
            "vendor_perf_breakdown_json": json.dumps(breakdown, default=str),
        })

        Snap = self.env["cm_sa.vendor_scorecard.snapshot"].sudo()
        Snap.create({
            "vendor_id": self.id,
            "period_start": window_start,
            "period_end": window_end,
            "score": score,
            "band": band,
            "on_time_pct": on_time_pct or 0.0,
            "avg_days_late": avg_days_late or 0.0,
            "price_variance_pct": var_pct or 0.0,
            "bill_dispute_count": dispute_n or 0,
            "receipt_count": receipt_n or 0,
            "breakdown_json": json.dumps(breakdown, default=str),
        })
        if hasattr(self, "message_post"):
            try:
                self.message_post(
                    body=_(
                        "Vendor scorecard snapshot: <b>%(score)s</b> "
                        "(band <b>%(band)s</b>) for %(s)s → %(e)s."
                    ) % {
                        "score": score,
                        "band": band,
                        "s": window_start,
                        "e": window_end,
                    },
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Cron entry
    # ------------------------------------------------------------------
    @api.model
    def _cron_compute_vendor_scores(self):
        config = self.env["cm_sa.vendor_scorecard.config"].sudo()._get_active()
        if not config:
            _logger.info("vendor_scorecard: no active config — cron skipped.")
            return
        # Pick partners with any PO activity in the window.
        today = fields.Date.context_today(self)
        window_start = today - timedelta(days=config.window_days)
        POL = self.env["purchase.order.line"].sudo()
        try:
            groups = POL.read_group(
                domain=[
                    ("date_order", ">=", fields.Datetime.to_string(
                        datetime.combine(window_start, datetime.min.time())
                    )),
                    ("state", "in", ("purchase", "done")),
                ],
                groupby=["partner_id"],
                fields=["partner_id"],
            )
        except Exception:
            groups = []
        ids = [g["partner_id"][0] for g in groups if g.get("partner_id")]
        # Also include partners with incoming receipts in window.
        try:
            pick_groups = self.env["stock.picking"].sudo().read_group(
                domain=[
                    ("picking_type_code", "=", "incoming"),
                    ("state", "=", "done"),
                    ("date_done", ">=", fields.Datetime.to_string(
                        datetime.combine(window_start, datetime.min.time())
                    )),
                ],
                groupby=["partner_id"],
                fields=["partner_id"],
            )
            for g in pick_groups:
                if g.get("partner_id"):
                    ids.append(g["partner_id"][0])
        except Exception:
            pass
        ids = list(set(ids))
        if not ids:
            return
        partners = self.sudo().browse(ids).exists()
        count = 0
        for p in partners:
            try:
                p._compute_and_store_vendor_score(config)
                count += 1
            except Exception:
                _logger.exception(
                    "vendor_scorecard: failed to score vendor %s (%s)",
                    p.id, p.display_name,
                )
        _logger.info("vendor_scorecard: scored %d vendor(s).", count)
