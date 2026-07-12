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
    def _cron_run_quotation_chase(self, force=False):
        """Iterate sent quotations with a schedule and send chase emails.

        Normal scheduled mode keeps the 1/3/7 due-date logic.
        Manual force mode is used by the dedicated manual scheduled action
        and sends the next pending chase step immediately for every eligible
        sent quotation.
        """
        orders = self.search([
            ("state", "=", "sent"),
            ("chase_paused", "=", False),
            ("chase_schedule_id", "!=", False),
        ])
        now = fields.Datetime.now()
        sent_count = 0
        for order in orders:
            try:
                if order._process_chase(now, force=force):
                    sent_count += 1
            except Exception:
                _logger.exception(
                    "Quotation Chase: failed to process SO id=%s", order.id,
                )
        _logger.info(
            "Quotation Chase: %s chase email(s) queued by %s run.",
            sent_count,
            "manual force" if force else "scheduled due",
        )
        return sent_count

    # ----------------------------------------------------------------------
    # Per-order processing
    # ----------------------------------------------------------------------
    def _process_chase(self, now=None, force=False):
        """Process one quotation.

        Cron mode keeps the normal schedule/due-date logic.
        Manual mode (force=True) sends the next pending chase step immediately,
        because the user explicitly clicked Run Chase Now from the quotation.
        """
        self.ensure_one()
        if now is None:
            now = fields.Datetime.now()

        # Stop conditions (defensive: cron domain already filters most of these)
        if self.state in ("sale", "done", "cancel"):
            return False
        if self.chase_paused or not self.chase_schedule_id:
            return False

        base_date = self.chase_last_sent or self.date_order
        if not base_date:
            return False

        # Customer-replied-since-base-date check
        if self._customer_replied_since(base_date):
            return False

        steps = self.chase_schedule_id.step_ids.sorted(lambda s: (s.sequence, s.id))
        next_step = None
        next_step_number = 0
        for step_number, step in enumerate(steps, start=1):
            # chase_step stores the functional step number, not the technical
            # drag-handle sequence. This avoids confusing values such as 10.
            if self.chase_step >= step_number:
                continue

            if force:
                next_step = step
                next_step_number = step_number
                break

            due_at = base_date + timedelta(days=step.days_after_send)
            if due_at <= now:
                next_step = step
                next_step_number = step_number
                break

        if not next_step:
            return False

        self._send_chase(next_step, next_step_number)
        return True

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
        """Manual trigger from the form button.

        This must send the next pending chase immediately and should not wait
        for the 1/3/7 day delay. The scheduled action still respects due dates.
        """
        sent_count = 0
        for order in self:
            if order._process_chase(force=True):
                sent_count += 1

        if sent_count:
            message = _("%s chase email(s) queued.") % sent_count
            notif_type = "success"
        else:
            message = _(
                "No chase email was sent. Please check that the quotation has "
                "a chase schedule, is not paused/cancelled/confirmed, has a "
                "remaining chase step, and has no customer reply after the last chase."
            )
            notif_type = "warning"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Quotation Chase"),
                "message": message,
                "type": notif_type,
                "sticky": False,
            },
        }
