import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ApprovalEscalationRule(models.Model):
    _name = "approval.escalation.rule"
    _description = "Approval Escalation Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(related="model_id.model", store=True, readonly=True)

    state_field = fields.Char(
        required=True,
        default="state",
        help="Name of the field holding the approval state (e.g. 'state', 'approval_state').",
    )
    pending_states = fields.Char(
        required=True,
        default="to approve",
        help="Comma-separated list of state values that mean 'awaiting action' "
             "(e.g. 'to approve,pending,submit').",
    )
    owner_field = fields.Char(
        default="user_id",
        help="Field pointing to the current approver (res.users). Used to detect who to nudge "
             "and whose manager to escalate to. Leave empty to skip reassignment.",
    )
    date_field = fields.Char(
        default="write_date",
        required=True,
        help="Field used to compute 'how long has this been stale'. Defaults to write_date. "
             "Typical alternatives: date_approve, create_date.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Optional extra Odoo domain filter appended to the state filter. "
             "Example: [('amount_total', '>', 1000)]",
    )

    step_ids = fields.One2many(
        "approval.escalation.step",
        "rule_id",
        copy=True,
    )
    log_ids = fields.One2many(
        "approval.escalation.log",
        "rule_id",
        readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("pending_states")
    def _check_pending_states(self):
        for rec in self:
            if not rec.pending_states.strip():
                raise ValidationError(_("At least one pending state must be set."))

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                domain = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(_("Extra domain is not a valid Python list: %s") % exc)
            if not isinstance(domain, list):
                raise ValidationError(_("Extra domain must evaluate to a list."))

    def _pending_state_list(self):
        self.ensure_one()
        return [s.strip() for s in self.pending_states.split(",") if s.strip()]

    def _build_domain(self):
        self.ensure_one()
        domain = [(self.state_field, "in", self._pending_state_list())]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _scan_stale_records(self):
        """Return list of (rule, step, record) triples that need escalation now."""
        self.ensure_one()
        Model = self.env[self.model_name]
        records = Model.search(self._build_domain())
        if not records:
            return []

        now = fields.Datetime.now()
        Log = self.env["approval.escalation.log"]
        pending = []
        for rec in records:
            try:
                stale_since = rec[self.date_field]
            except KeyError:
                continue
            if not stale_since:
                continue
            hours_stale = (now - stale_since).total_seconds() / 3600.0
            already = Log.search([
                ("rule_id", "=", self.id),
                ("res_model", "=", self.model_name),
                ("res_id", "=", rec.id),
            ])
            fired_step_ids = already.step_id.ids
            for step in self.step_ids.sorted("after_hours"):
                if step.id in fired_step_ids:
                    continue
                if hours_stale >= step.after_hours:
                    pending.append((step, rec))
        return pending

    @api.model
    def _cron_run_escalations(self):
        for rule in self.search([]):
            for step, record in rule._scan_stale_records():
                try:
                    step._apply_to(record)
                except Exception:
                    _logger.exception(
                        "ApprovalEscalation: step %s failed on %s,%s",
                        step.id, rule.model_name, record.id,
                    )
                    continue

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Escalation Log"),
            "res_model": "approval.escalation.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }


class ApprovalEscalationStep(models.Model):
    _name = "approval.escalation.step"
    _description = "Approval Escalation Step"
    _order = "after_hours"

    rule_id = fields.Many2one(
        "approval.escalation.rule",
        required=True,
        ondelete="cascade",
    )
    after_hours = fields.Float(
        string="Trigger after (hours)",
        required=True,
        default=24.0,
        help="Fire this step when the record has been pending for this many hours.",
    )
    action = fields.Selection(
        [
            ("notify", "Notify current approver"),
            ("escalate_manager", "Reassign to approver's manager"),
            ("escalate_user", "Reassign to a specific user"),
            ("notify_user", "Notify a specific user"),
        ],
        required=True,
        default="notify",
    )
    target_user_id = fields.Many2one(
        "res.users",
        help="Used when action is 'escalate_user' or 'notify_user'.",
    )
    mail_template_id = fields.Many2one(
        "mail.template",
        domain="[('model_id', '=', False)]",
        help="Optional email template. If empty, a default reminder message is posted.",
    )

    def _apply_to(self, record):
        self.ensure_one()
        rule = self.rule_id
        new_owner = self._resolve_target(record)
        body = self._render_body(record, new_owner)

        record.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

        if self.action in ("escalate_manager", "escalate_user") and new_owner and rule.owner_field:
            try:
                record.write({rule.owner_field: new_owner.id})
            except Exception:
                pass

        if new_owner:
            record.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=new_owner.id,
                summary=_("Stale approval: %s") % record.display_name,
                note=body,
            )

        self.env["approval.escalation.log"].create({
            "rule_id": rule.id,
            "step_id": self.id,
            "res_model": rule.model_name,
            "res_id": record.id,
            "escalated_to_id": new_owner.id if new_owner else False,
            "body": body,
        })

    def _resolve_target(self, record):
        self.ensure_one()
        rule = self.rule_id
        current_owner = False
        if rule.owner_field:
            try:
                current_owner = record[rule.owner_field]
            except KeyError:
                current_owner = False
        if self.action in ("notify_user", "escalate_user"):
            return self.target_user_id
        if self.action == "escalate_manager":
            partner = current_owner.employee_id.parent_id.user_id if current_owner else False
            return partner or current_owner
        return current_owner

    def _render_body(self, record, target):
        self.ensure_one()
        if self.mail_template_id:
            return self.mail_template_id._render_field("body_html", [record.id])[record.id]
        hours = int(self.after_hours)
        who = target.name if target else _("the owner")
        return _(
            "<p>This record has been pending for more than %(h)s hours. "
            "Escalation step '%(action)s' fired — notifying <b>%(who)s</b>.</p>"
        ) % {"h": hours, "action": dict(self._fields["action"].selection)[self.action], "who": who}
