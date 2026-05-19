import logging
from datetime import timedelta
from difflib import SequenceMatcher

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

DEDUP_MOVE_TYPES = ("in_invoice", "in_refund")


def _ratio(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


class AccountMove(models.Model):
    _inherit = "account.move"

    dedup_candidate_ids = fields.Many2many(
        "account.move",
        "cm_sa_dedup_candidate_rel",
        "move_id",
        "candidate_id",
        string="Duplicate Candidates",
        compute="_compute_dedup",
        store=False,
    )
    dedup_score = fields.Float(
        string="Duplicate Score",
        compute="_compute_dedup",
        store=False,
        help="Highest combined similarity (0-1) with any other vendor bill.",
    )
    dedup_warning = fields.Text(
        compute="_compute_dedup",
        store=False,
    )
    dedup_has_warning = fields.Boolean(
        compute="_compute_dedup",
        store=False,
    )

    def _get_dedup_params(self):
        ICP = self.env["ir.config_parameter"].sudo()
        def f(key, default):
            val = ICP.get_param("cm_sa_bill_dedup." + key, default)
            try:
                return float(val)
            except (TypeError, ValueError):
                return float(default)
        def i(key, default):
            val = ICP.get_param("cm_sa_bill_dedup." + key, default)
            try:
                return int(val)
            except (TypeError, ValueError):
                return int(default)
        def b(key, default):
            val = ICP.get_param("cm_sa_bill_dedup." + key, default)
            return str(val).strip().lower() in ("1", "true", "yes", "on")
        return {
            "threshold": f("threshold", 0.8),
            "window_days": i("window_days", 90),
            "amount_tolerance": f("amount_tolerance", 0.01),
            "date_tolerance_days": i("date_tolerance_days", 5),
            "check_amount": b("check_amount", True),
            "check_date": b("check_date", True),
        }

    @api.depends("partner_id", "ref", "amount_total", "invoice_date", "state",
                 "move_type")
    def _compute_dedup(self):
        params = self._get_dedup_params()
        for move in self:
            move.dedup_candidate_ids = [(5, 0, 0)]
            move.dedup_score = 0.0
            move.dedup_warning = ""
            move.dedup_has_warning = False
            if move.move_type not in DEDUP_MOVE_TYPES:
                continue
            if move.state not in ("draft", "posted"):
                continue
            if not move.partner_id:
                continue
            move._populate_dedup(params)

    def _populate_dedup(self, params):
        self.ensure_one()
        window = params["window_days"]
        anchor_date = self.invoice_date or fields.Date.context_today(self)
        start = anchor_date - timedelta(days=window)
        end = anchor_date + timedelta(days=window)
        domain = [
            ("id", "!=", self.id or 0),
            ("partner_id", "=", self.partner_id.id),
            ("move_type", "in", list(DEDUP_MOVE_TYPES)),
            ("state", "in", ("draft", "posted")),
            ("invoice_date", ">=", fields.Date.to_string(start)),
            ("invoice_date", "<=", fields.Date.to_string(end)),
        ]
        candidates = self.sudo().search(domain, limit=50)
        best_score = 0.0
        matches = self.env["account.move"]
        for cand in candidates:
            score = self._score_against(cand, params)
            if score >= params["threshold"]:
                matches |= cand
            if score > best_score:
                best_score = score
        self.dedup_candidate_ids = [(6, 0, matches.ids)]
        self.dedup_score = best_score
        self.dedup_has_warning = best_score >= params["threshold"] and bool(matches)
        if self.dedup_has_warning:
            names = ", ".join(m.display_name for m in matches[:5])
            self.dedup_warning = _(
                "Possible duplicate (score %(score).2f). Candidates: %(names)s"
            ) % {"score": best_score, "names": names}
        else:
            self.dedup_warning = ""

    def _score_against(self, other, params):
        """Combined similarity in [0,1]. Weighted mean of reference similarity,
        amount-within-tolerance, and date-within-tolerance."""
        self.ensure_one()
        parts = []
        weights = []
        ref_sim = _ratio(self.ref or "", other.ref or "")
        parts.append(ref_sim)
        weights.append(2.0)  # ref has extra weight
        if params["check_amount"]:
            tol = params["amount_tolerance"]
            a = abs(self.amount_total or 0.0)
            b = abs(other.amount_total or 0.0)
            if max(a, b) == 0:
                parts.append(0.0)
            else:
                diff = abs(a - b) / max(a, b)
                parts.append(1.0 if diff <= tol else max(0.0, 1.0 - diff))
            weights.append(1.5)
        if params["check_date"]:
            tol = params["date_tolerance_days"]
            if self.invoice_date and other.invoice_date:
                delta = abs((self.invoice_date - other.invoice_date).days)
                parts.append(1.0 if delta <= tol else max(0.0, 1.0 - delta / (tol * 4.0 + 1)))
            else:
                parts.append(0.0)
            weights.append(1.0)
        total = sum(w for w in weights)
        if total == 0:
            return 0.0
        return sum(p * w for p, w in zip(parts, weights)) / total

    def action_view_dedup_candidates(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Duplicate Candidates"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.dedup_candidate_ids.ids)],
        }

    def action_log_dedup_review(self):
        """Create a dedup review log entry (pending) for each candidate
        of the current move. Admins can then triage them."""
        self.ensure_one()
        Log = self.env["cm_sa.dedup.review.log"]
        for cand in self.dedup_candidate_ids:
            existing = Log.search_count([
                ("checked_move_id", "=", self.id),
                ("candidate_move_id", "=", cand.id),
            ])
            if existing:
                continue
            Log.create({
                "checked_move_id": self.id,
                "candidate_move_id": cand.id,
                "score": self.dedup_score,
                "review_status": "pending",
            })
        if hasattr(self, "message_post"):
            try:
                self.message_post(
                    body=_(
                        "Duplicate-review log opened against %(n)s candidate(s)."
                    ) % {"n": len(self.dedup_candidate_ids)},
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:
                pass
        return {
            "type": "ir.actions.act_window",
            "name": _("Duplicate Review"),
            "res_model": "cm_sa.dedup.review.log",
            "view_mode": "list,form",
            "domain": [("checked_move_id", "=", self.id)],
        }
