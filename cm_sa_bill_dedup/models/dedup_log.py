from odoo import _, fields, models


class CmSaDedupReviewLog(models.Model):
    _name = "cm_sa.dedup.review.log"
    _description = "Vendor Bill Duplicate Review Log"
    _order = "create_date desc, id desc"

    checked_move_id = fields.Many2one(
        "account.move",
        string="Checked Bill",
        required=True,
        ondelete="cascade",
        index=True,
    )
    candidate_move_id = fields.Many2one(
        "account.move",
        string="Candidate Bill",
        required=True,
        ondelete="cascade",
        index=True,
    )
    score = fields.Float(digits=(4, 3))
    review_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("false_positive", "False positive"),
            ("confirmed_duplicate", "Confirmed duplicate"),
            ("resolved", "Resolved"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    reviewed_by = fields.Many2one("res.users", string="Reviewed By")
    reviewed_at = fields.Datetime(string="Reviewed At")
    notes = fields.Text()

    _uniq_pair = models.Constraint(
        "unique(checked_move_id, candidate_move_id)",
        "A review log for this bill pair already exists.",
    )

    def _mark(self, status):
        self.write({
            "review_status": status,
            "reviewed_by": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        })
        # chatter on both
        for rec in self:
            for move in (rec.checked_move_id, rec.candidate_move_id):
                if hasattr(move, "message_post"):
                    try:
                        move.message_post(
                            body=_(
                                "Duplicate review marked as <b>%s</b> by %s."
                            ) % (status, self.env.user.display_name),
                            message_type="comment",
                            subtype_xmlid="mail.mt_note",
                        )
                    except Exception:
                        pass
        return True

    def action_mark_false_positive(self):
        return self._mark("false_positive")

    def action_mark_confirmed_duplicate(self):
        return self._mark("confirmed_duplicate")

    def action_mark_resolved(self):
        return self._mark("resolved")
