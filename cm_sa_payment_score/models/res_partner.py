import json
import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    payment_score_total = fields.Integer(
        string="Payment Score",
        readonly=True,
        copy=False,
        index=True,
    )
    payment_score_band = fields.Selection(
        [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        string="Score Band",
        readonly=True,
        copy=False,
        index=True,
    )
    payment_score_updated_at = fields.Datetime(
        string="Score Updated At",
        readonly=True,
        copy=False,
    )
    payment_score_breakdown_json = fields.Text(
        string="Score Breakdown (JSON)",
        readonly=True,
        copy=False,
    )

    payment_score_snapshot_ids = fields.One2many(
        "cm_sa.payment_score.snapshot",
        "partner_id",
        string="Score History",
        readonly=True,
    )
    payment_score_snapshot_count = fields.Integer(
        compute="_compute_payment_score_snapshot_count",
    )

    @api.depends("payment_score_snapshot_ids")
    def _compute_payment_score_snapshot_count(self):
        for rec in self:
            rec.payment_score_snapshot_count = len(rec.payment_score_snapshot_ids)

    def action_view_payment_score_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payment Score History"),
            "res_model": "cm_sa.payment_score.snapshot",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_compute_payment_score(self):
        """Recompute the score for the current recordset. Callable from
        the partner form as an admin action."""
        config = self.env["cm_sa.payment_score.config"].sudo()._get_active()
        if not config:
            return
        for rec in self:
            rec._compute_and_store_payment_score(config)
        return True

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _payment_score_window_invoices(self, window_start):
        """Return posted customer invoices for this partner within window."""
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        return Move.search([
            ("partner_id", "=", self.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", fields.Date.to_string(window_start)),
        ])

    def _payment_score_metric_days_late(self, invoices):
        """Metric A — average days late on paid invoices.
        0 late -> 100 pts, linear falloff, 60+ days late -> 0 pts.
        Uses invoice_date_due and the latest payment/reconcile date
        approximated by the move's last chatter date or, if in_payment,
        today."""
        if not invoices:
            return {"score": None, "sample": 0, "avg_days_late": 0.0}
        paid = invoices.filtered(lambda m: m.payment_state in (
            "paid", "in_payment", "reversed",
        ))
        if not paid:
            return {"score": None, "sample": 0, "avg_days_late": 0.0}
        total = 0.0
        counted = 0
        for inv in paid:
            due = inv.invoice_date_due or inv.invoice_date
            if not due:
                continue
            # Best-effort "paid-on" proxy: use the reconciliation partial
            # max date, falling back to write_date of the invoice.
            paid_on = self._payment_score_paid_on(inv)
            if not paid_on:
                continue
            days_late = max(0, (paid_on - due).days)
            total += days_late
            counted += 1
        if not counted:
            return {"score": None, "sample": 0, "avg_days_late": 0.0}
        avg = total / counted
        # 0..60 days -> 100..0 linear
        pts = max(0.0, min(100.0, 100.0 * (1.0 - avg / 60.0)))
        return {"score": pts, "sample": counted, "avg_days_late": round(avg, 2)}

    @staticmethod
    def _payment_score_paid_on(inv):
        """Return the approximate date the invoice was fully paid.

        Uses the reconciled partial's max write_date; falls back to the
        invoice's write_date. Robust to missing account modules."""
        try:
            partials = inv.line_ids.matched_debit_ids | inv.line_ids.matched_credit_ids
            dates = [p.max_date for p in partials if p.max_date]
            if dates:
                return max(dates)
        except Exception:
            pass
        wd = inv.write_date
        if isinstance(wd, datetime):
            return wd.date()
        if isinstance(wd, date):
            return wd
        return False

    def _payment_score_metric_partial(self, invoices):
        """Metric B — share of invoices that spent time partially paid."""
        if not invoices:
            return {"score": None, "ratio": 0.0, "sample": 0}
        partial = invoices.filtered(lambda m: m.payment_state == "partial")
        ratio = len(partial) / len(invoices)
        # 0% partial -> 100 pts, 50%+ partial -> 0 pts
        pts = max(0.0, min(100.0, 100.0 * (1.0 - (ratio / 0.5))))
        return {"score": pts, "ratio": round(ratio, 3), "sample": len(invoices)}

    def _payment_score_metric_stretch(self):
        """Metric C — overdue residual / credit_limit."""
        self.ensure_one()
        try:
            credit_limit = float(self.credit_limit or 0.0)
        except Exception:
            credit_limit = 0.0
        if credit_limit <= 0:
            return {"score": None, "ratio": None}
        today = fields.Date.context_today(self)
        Move = self.env["account.move"].sudo()
        overdue = Move.search([
            ("partner_id", "=", self.id),
            ("move_type", "in", ("out_invoice",)),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("invoice_date_due", "<", fields.Date.to_string(today)),
        ])
        residual = sum(overdue.mapped("amount_residual") or [0.0])
        ratio = residual / credit_limit if credit_limit else 0.0
        # 0 stretch -> 100, 1.0 stretch -> 0
        pts = max(0.0, min(100.0, 100.0 * (1.0 - ratio)))
        return {"score": pts, "ratio": round(ratio, 3)}

    def _payment_score_metric_on_time(self, invoices):
        """Metric D — % of in-window invoices paid on/before due date."""
        if not invoices:
            return {"score": None, "ratio": 0.0, "sample": 0}
        paid = invoices.filtered(lambda m: m.payment_state in (
            "paid", "in_payment", "reversed",
        ))
        if not paid:
            return {"score": None, "ratio": 0.0, "sample": 0}
        on_time = 0
        for inv in paid:
            due = inv.invoice_date_due or inv.invoice_date
            if not due:
                continue
            paid_on = self._payment_score_paid_on(inv)
            if paid_on and paid_on <= due:
                on_time += 1
        ratio = on_time / len(paid)
        pts = max(0.0, min(100.0, 100.0 * ratio))
        return {"score": pts, "ratio": round(ratio, 3), "sample": len(paid)}

    def _compute_and_store_payment_score(self, config):
        """Compute + persist + snapshot-if-month-changed for one partner."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        window_start = today - timedelta(days=config.window_days)
        invoices = self._payment_score_window_invoices(window_start)

        m_days = self._payment_score_metric_days_late(invoices)
        m_partial = self._payment_score_metric_partial(invoices)
        m_stretch = self._payment_score_metric_stretch()
        m_ontime = self._payment_score_metric_on_time(invoices)

        # Weighted sum of available metrics (skip missing).
        comps = [
            (m_days["score"], config.weight_days_late, "days_late"),
            (m_partial["score"], config.weight_partial, "partial"),
            (m_stretch["score"], config.weight_stretch, "stretch"),
            (m_ontime["score"], config.weight_on_time, "on_time"),
        ]
        num = 0.0
        den = 0.0
        for pts, w, _label in comps:
            if pts is None or w <= 0:
                continue
            num += pts * w
            den += w
        if den <= 0:
            score = 0
        else:
            score = int(round(num / den))
        score = max(0, min(100, score))
        band = config.band_for_score(score)

        breakdown = {
            "window_days": config.window_days,
            "invoices_in_window": len(invoices),
            "avg_days_late": m_days.get("avg_days_late"),
            "partial_ratio": m_partial.get("ratio"),
            "stretch_ratio": m_stretch.get("ratio"),
            "on_time_ratio": m_ontime.get("ratio"),
            "weights": {
                "days_late": config.weight_days_late,
                "partial": config.weight_partial,
                "stretch": config.weight_stretch,
                "on_time": config.weight_on_time,
            },
            "metric_points": {
                "days_late": m_days.get("score"),
                "partial": m_partial.get("score"),
                "stretch": m_stretch.get("score"),
                "on_time": m_ontime.get("score"),
            },
            "score": score,
            "band": band,
        }

        vals = {
            "payment_score_total": score,
            "payment_score_band": band,
            "payment_score_updated_at": fields.Datetime.now(),
            "payment_score_breakdown_json": json.dumps(breakdown, default=str),
        }
        self.sudo().write(vals)

        Snap = self.env["cm_sa.payment_score.snapshot"].sudo()
        period_year = today.year
        period_month = today.month
        existing = Snap.search([
            ("partner_id", "=", self.id),
            ("period_year", "=", period_year),
            ("period_month", "=", period_month),
        ], limit=1)
        if not existing:
            Snap.create({
                "partner_id": self.id,
                "period_year": period_year,
                "period_month": period_month,
                "score": score,
                "band": band,
                "breakdown_json": json.dumps(breakdown, default=str),
            })
            if hasattr(self, "message_post"):
                try:
                    self.message_post(
                        body=_(
                            "Payment score snapshot: <b>%(score)s</b> "
                            "(band <b>%(band)s</b>) for %(m)04d-%(mm)02d."
                        ) % {
                            "score": score,
                            "band": band,
                            "m": period_year,
                            "mm": period_month,
                        },
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_compute_payment_scores(self):
        """Nightly cron. Picks all partners with any invoice activity in
        the window and scores them."""
        config = self.env["cm_sa.payment_score.config"].sudo()._get_active()
        if not config:
            _logger.info("payment_score: no active config — cron skipped.")
            return
        today = fields.Date.context_today(self)
        window_start = today - timedelta(days=config.window_days)
        Move = self.env["account.move"].sudo()
        partner_ids = Move.read_group(
            domain=[
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("invoice_date", ">=", fields.Date.to_string(window_start)),
            ],
            groupby=["partner_id"],
            fields=["partner_id"],
        )
        ids = [g["partner_id"][0] for g in partner_ids if g.get("partner_id")]
        if not ids:
            return
        partners = self.sudo().browse(ids).exists()
        count = 0
        for p in partners:
            try:
                p._compute_and_store_payment_score(config)
                count += 1
            except Exception:
                _logger.exception(
                    "payment_score: failed to score partner %s (%s)",
                    p.id, p.display_name,
                )
        _logger.info("payment_score: scored %d partner(s).", count)
