import logging
from datetime import timedelta

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    chase_schedule_id = fields.Many2one(
        "cm_sa.chase.schedule",
        string="Chase Schedule",
        domain="[('active', '=', True)]",
        help="Pick a follow-up cadence. Leave empty to disable chasing for this quotation.",
    )
    chase_paused = fields.Boolean(
        string="Pause Chase",
        default=False,
        copy=False,
        help="Stop sending chase emails for this quotation without losing the schedule.",
    )
    chase_last_sent = fields.Datetime(
        string="Last Chase Sent",
        readonly=True,
        copy=False,
    )
    chase_step = fields.Integer(
        string="Chase Step",
        default=0,
        readonly=True,
        copy=False,
        help="Number of chase emails already sent for this quotation.",
    )

    def copy(self, default=None):
        """Reset runtime chase data when duplicating a quotation.

        The schedule itself may be copied, but the new quotation must start a
        fresh chase cycle.
        """
        default = dict(default or {})
        default.setdefault("chase_paused", False)
        default.setdefault("chase_step", 0)
        default.setdefault("chase_last_sent", False)
        return super().copy(default)

    # ----------------------------------------------------------------------
    # Cron entry point
    # ----------------------------------------------------------------------
    def _cron_run_quotation_chase(self):
        """Iterate every sent quotation with a schedule and send the next due chase."""
        orders = self.search([
            ("state", "=", "sent"),
            ("chase_paused", "=", False),
            ("chase_schedule_id", "!=", False),
        ])
        now = fields.Datetime.now()
        for order in orders:
            try:
                order._process_chase(now)
            except Exception:
                _logger.exception(
                    "Quotation Chase: failed to process SO id=%s", order.id,
                )

    # ----------------------------------------------------------------------
    # Per-order processing
    # ----------------------------------------------------------------------
    def _process_chase(self, now=None):
        self.ensure_one()
        if now is None:
            now = fields.Datetime.now()

        # Stop conditions (defensive: cron domain already filters most of these)
        if self.state in ("sale", "done", "cancel"):
            return
        if self.chase_paused or not self.chase_schedule_id:
            return

        base_date = self.chase_last_sent or self.date_order
        if not base_date:
            return

        # Customer-replied-since-base-date check
        if self._customer_replied_since(base_date):
            return

        steps = self.chase_schedule_id.step_ids.sorted(lambda s: (s.sequence, s.id))
        next_step = None
        next_step_number = 0
        for step_number, step in enumerate(steps, start=1):
            # chase_step stores the functional step number, not the technical
            # drag-handle sequence. This avoids confusing values such as 10.
            if self.chase_step >= step_number:
                continue
            due_at = base_date + timedelta(days=step.days_after_send)
            if due_at <= now:
                next_step = step
                next_step_number = step_number
                break

        if not next_step:
            return

        self._send_chase(next_step, next_step_number)

    def _customer_replied_since(self, since):
        """Return True if the customer (partner_id) sent an email on this SO since `since`."""
        self.ensure_one()
        if not self.partner_id:
            return False
        Message = self.env["mail.message"].sudo()
        msg = Message.search(
            [
                ("model", "=", "sale.order"),
                ("res_id", "=", self.id),
                ("message_type", "=", "email"),
                ("author_id", "=", self.partner_id.id),
                ("date", ">=", since),
            ],
            limit=1,
        )
        return bool(msg)

    def _send_chase(self, step, step_number=False):
        """Render & send the step's template, advance counters, post chatter note."""
        self.ensure_one()
        template = step.mail_template_id
        if not template:
            return

        if not step_number:
            steps = self.chase_schedule_id.step_ids.sorted(lambda s: (s.sequence, s.id))
            step_number = steps.ids.index(step.id) + 1 if step.id in steps.ids else step.sequence

        template.send_mail(
            self.id,
            force_send=False,
            email_layout_xmlid="mail.mail_notification_light",
        )

        self.write({
            "chase_step": step_number,
            "chase_last_sent": fields.Datetime.now(),
        })

        self.message_post(
            body=_(
                "Sent chase #%(num)s via %(schedule)s."
            ) % {
                "num": step_number,
                "schedule": self.chase_schedule_id.name or "",
            },
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    # ----------------------------------------------------------------------
    # UI helpers
    # ----------------------------------------------------------------------
    def action_chase_run_now(self):
        """Manual trigger from the form button — process this single SO immediately."""
        for order in self:
            order._process_chase()
        return True
