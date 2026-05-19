import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Date

_logger = logging.getLogger(__name__)


class ActivityReassignWizard(models.TransientModel):
    _name = "cm_sa.activity.reassign.wizard"
    _description = "Bulk Activity Reassignment Wizard"

    from_user_id = fields.Many2one(
        "res.users",
        string="From user",
        required=True,
        help="Activities currently owned by this user will be transferred.",
    )
    to_user_id = fields.Many2one(
        "res.users",
        string="To user",
        required=True,
        help="The new owner for every reassigned activity.",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Restrict to model",
        help="Leave blank to reassign activities across every model.",
    )
    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Activity type",
        help="Optional — restrict the bulk operation to one activity type.",
    )
    date_deadline_from = fields.Date(string="Deadline from")
    date_deadline_to = fields.Date(string="Deadline to")
    overdue_only = fields.Boolean(
        string="Overdue only",
        default=False,
        help="If set, only activities with a deadline before today are reassigned.",
    )
    new_deadline = fields.Date(
        string="New deadline",
        help="Optional — if set, every reassigned activity is rescheduled to this date.",
    )

    count_to_reassign = fields.Integer(
        string="Matching activities",
        compute="_compute_count",
        readonly=True,
        store=False,
    )
    preview_text = fields.Text(
        string="Preview",
        compute="_compute_count",
        readonly=True,
        store=False,
    )

    # ------------------------------------------------------------------
    # Domain & compute
    # ------------------------------------------------------------------

    def _build_domain(self):
        self.ensure_one()
        if not self.from_user_id:
            return []
        domain = [("user_id", "=", self.from_user_id.id)]
        if self.model_id:
            domain.append(("res_model", "=", self.model_id.model))
        if self.activity_type_id:
            domain.append(("activity_type_id", "=", self.activity_type_id.id))
        if self.overdue_only:
            domain.append(("date_deadline", "<", fields.Date.context_today(self)))
        else:
            if self.date_deadline_from:
                domain.append(("date_deadline", ">=", self.date_deadline_from))
            if self.date_deadline_to:
                domain.append(("date_deadline", "<=", self.date_deadline_to))
        return domain

    @api.depends(
        "from_user_id",
        "to_user_id",
        "model_id",
        "activity_type_id",
        "date_deadline_from",
        "date_deadline_to",
        "overdue_only",
        "new_deadline",
    )
    def _compute_count(self):
        Activity = self.env["mail.activity"].sudo()
        for wiz in self:
            if not wiz.from_user_id:
                wiz.count_to_reassign = 0
                wiz.preview_text = _(
                    "Pick the source user to see how many activities will be transferred."
                )
                continue
            domain = wiz._build_domain()
            count = Activity.search_count(domain)
            wiz.count_to_reassign = count
            target = wiz.to_user_id.display_name or _("(target user not set)")
            wiz.preview_text = _(
                "Found %(n)s activities owned by %(src)s matching the current "
                "filters. They will be transferred to %(dst)s when you press Apply."
            ) % {
                "n": count,
                "src": wiz.from_user_id.display_name,
                "dst": target,
            }

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_refresh_count(self):
        self.ensure_one()
        # Recompute is automatic on dependency change; this button forces
        # a re-render by reopening the wizard with the same record.
        self._compute_count()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_reassign(self):
        self.ensure_one()
        if not self.to_user_id:
            raise UserError(_("Please pick the user that should receive the activities."))
        if self.from_user_id == self.to_user_id:
            raise UserError(_("Source and target users must be different."))

        Activity = self.env["mail.activity"].sudo()
        activities = Activity.search(self._build_domain())
        if not activities:
            raise UserError(_("No activities match the current filters."))

        write_vals = {"user_id": self.to_user_id.id}
        if self.new_deadline:
            write_vals["date_deadline"] = self.new_deadline

        from_user = self.from_user_id
        to_user = self.to_user_id

        # Group by parent record so we post one chatter line per activity, but
        # only on records that actually inherit mail.thread.
        for activity in activities:
            summary = activity.summary or (
                activity.activity_type_id.name if activity.activity_type_id else _("Activity")
            )
            parent_model = activity.res_model
            parent_id = activity.res_id
            activity.write(write_vals)
            if not parent_model or not parent_id:
                continue
            Model = self.env.get(parent_model)
            if Model is None:
                continue
            if not hasattr(Model, "message_post"):
                continue
            try:
                record = self.env[parent_model].sudo().browse(parent_id).exists()
                if not record:
                    continue
                record.message_post(
                    body=_(
                        "Activity '%(summary)s' reassigned from %(src)s to %(dst)s."
                    ) % {
                        "summary": summary,
                        "src": from_user.name,
                        "dst": to_user.name,
                    },
                )
            except Exception as exc:  # pragma: no cover - defensive
                _logger.warning(
                    "cm_sa_activity_reassign: chatter post failed on %s,%s: %s",
                    parent_model, parent_id, exc,
                )

        count = len(activities)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reassigned"),
                "message": _("%s activities transferred.") % count,
                "type": "success",
                "sticky": False,
            },
        }

    # ------------------------------------------------------------------
    # Server-action entry point (from res.users form)
    # ------------------------------------------------------------------

    @api.model
    def action_open_from_user(self):
        """Called by the contextual server action on res.users."""
        active_id = self.env.context.get("active_id")
        active_model = self.env.context.get("active_model")
        from_user = False
        if active_model == "res.users" and active_id:
            from_user = self.env["res.users"].browse(active_id)
        ctx = dict(self.env.context)
        if from_user:
            ctx["default_from_user_id"] = from_user.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Reassign Activities"),
            "res_model": "cm_sa.activity.reassign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }
