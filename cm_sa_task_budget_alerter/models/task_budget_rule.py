import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CmSaTaskBudgetRule(models.Model):
    _name = "cm_sa.task.budget.rule"
    _description = "Task Time-Budget Alert Rule"
    _order = "name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    thresholds_csv = fields.Char(
        string="Thresholds (%)",
        default="75,90,100",
        required=True,
        help="Comma-separated percentages. Examples: '75,90,100' or '5%'. "
             "An alert is generated the first time a task's consumed hours "
             "cross each threshold.",
    )
    notify_assignee = fields.Boolean(
        default=True,
        help="Email the task's assignee (user_ids) on threshold crossing.",
    )
    notify_manager = fields.Boolean(
        default=True,
        help="Email the project manager (user_id on project.project) on threshold crossing.",
    )
    extra_notify_user_ids = fields.Many2many(
        "res.users",
        "cm_sa_task_budget_rule_extra_rel",
        "rule_id", "user_id",
        string="Extra Recipients",
        help="Optional additional users (e.g. PMO, finance) to notify.",
    )
    project_ids = fields.Many2many(
        "project.project",
        "cm_sa_task_budget_rule_project_rel",
        "rule_id", "project_id",
        string="Apply to Projects",
        help="Leave empty to apply across all projects.",
    )
    exclude_stage_ids = fields.Many2many(
        "project.task.type",
        "cm_sa_task_budget_rule_stage_rel",
        "rule_id", "stage_id",
        string="Exclude Stages",
        help="Tasks in these stages are skipped (typical: Done, Cancelled).",
    )
    min_planned_hours = fields.Float(
        string="Minimum Planned Hours",
        default=1.0,
        help="Ignore tasks with planned/allocated hours below this value. Filters "
             "throwaway tasks with 0.1h placeholders.",
    )

    last_run = fields.Datetime(readonly=True)
    log_ids = fields.One2many(
        "cm_sa.task.budget.alert.log", "rule_id", readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A task-budget rule with this name already exists.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("thresholds_csv")
    def _check_thresholds(self):
        for rec in self:
            try:
                ths = rec._parse_thresholds()
            except Exception as exc:
                raise ValidationError(_(
                    "Thresholds must be a comma-separated list of positive "
                    "percentages (e.g. '75,90,100' or '5%%'): %s"
                ) % exc)
            if not ths:
                raise ValidationError(_("At least one threshold is required."))
            if any(t <= 0 for t in ths):
                raise ValidationError(_("Thresholds must be positive."))

    @api.constrains("min_planned_hours")
    def _check_min_planned(self):
        for rec in self:
            if rec.min_planned_hours < 0:
                raise ValidationError(_("Min Planned Hours must be >= 0."))

    def _parse_thresholds(self):
        """Return a sorted list of integer thresholds.

        Accepts both '5' and '5%' so users can enter the value naturally in
        the Thresholds (%) field.
        """
        self.ensure_one()
        if not self.thresholds_csv:
            return []
        thresholds = set()
        parts = [p.strip() for p in re.split(r"[,\s]+", self.thresholds_csv) if p.strip()]
        for part in parts:
            clean = part.rstrip("%").strip()
            value = float(clean)
            if not value.is_integer():
                raise ValueError(_("Decimal thresholds are not supported: %s") % part)
            thresholds.add(int(value))
        return sorted(thresholds)

    def _project_domain(self):
        self.ensure_one()
        return [("id", "in", self.project_ids.ids)] if self.project_ids else []

    def _candidate_domain(self):
        """Return the DB search domain.

        Important: we intentionally do not filter on planned_hours here.
        In some Odoo 19 databases the UI value can be stored/displayed through
        allocated_hours while planned_hours exists but remains zero. Filtering
        by only planned_hours can silently skip valid tasks, which was the
        reason alerts were not generated in testing.
        """
        self.ensure_one()
        domain = []
        if self.project_ids:
            domain += [("project_id", "in", self.project_ids.ids)]
        if self.exclude_stage_ids:
            domain += [("stage_id", "not in", self.exclude_stage_ids.ids)]
        return domain

    def _get_planned_hours(self, task):
        """Return the configured/allocated hours using the field available in DB."""
        for fname in ("planned_hours", "allocated_hours"):
            if fname in task._fields:
                value = task[fname] or 0.0
                if value > 0:
                    return value
        return 0.0

    def _get_effective_hours(self, task):
        """Return logged hours using the best Odoo field available.

        Odoo versions/customizations may expose the timesheet total as
        effective_hours or total_hours_spent. If both are zero, fall back to
        summing timesheet_ids.unit_amount.
        """
        for fname in ("effective_hours", "total_hours_spent"):
            if fname in task._fields:
                value = task[fname] or 0.0
                if value > 0:
                    return value

        if "timesheet_ids" in task._fields:
            try:
                return sum(task.timesheet_ids.mapped("unit_amount"))
            except Exception:
                _logger.exception("TaskBudgetAlerter: could not sum task timesheets")
        return 0.0

    def _compute_percent(self, task, planned=None, effective=None):
        planned = self._get_planned_hours(task) if planned is None else planned
        effective = self._get_effective_hours(task) if effective is None else effective
        if planned <= 0:
            return 0.0
        return effective / planned * 100.0

    def _run_one(self):
        self.ensure_one()
        if not self.active:
            return 0

        Task = self.env["project.task"].sudo()
        Log = self.env["cm_sa.task.budget.alert.log"].sudo()

        try:
            thresholds = self._parse_thresholds()
        except Exception:
            _logger.exception("TaskBudgetAlerter rule %s: bad thresholds", self.name)
            return 0
        if not thresholds:
            return 0

        try:
            tasks = Task.search(self._candidate_domain())
        except Exception as exc:
            _logger.exception(
                "TaskBudgetAlerter rule %s: search failed: %s", self.name, exc,
            )
            return 0

        generated = 0
        for task in tasks:
            planned = self._get_planned_hours(task)
            if planned <= 0 or planned < self.min_planned_hours:
                continue

            effective = self._get_effective_hours(task)
            pct = self._compute_percent(task, planned=planned, effective=effective)
            if pct <= 0:
                continue

            # Identify thresholds now crossed but not yet alerted.
            crossed = [t for t in thresholds if pct >= t]
            if not crossed:
                continue

            already = Log.search([
                ("rule_id", "=", self.id),
                ("task_id", "=", task.id),
                ("threshold_pct", "in", crossed),
            ]).mapped("threshold_pct")
            pending = [t for t in crossed if t not in already]
            if not pending:
                continue

            recipients = self._resolve_recipients(task)
            for t in pending:
                try:
                    Log.create({
                        "rule_id": self.id,
                        "task_id": task.id,
                        "project_id": task.project_id.id if task.project_id else False,
                        "threshold_pct": t,
                        "percent_at_alert": pct,
                        "planned_hours": planned,
                        "effective_hours": effective,
                    })
                    generated += 1
                except Exception:
                    _logger.exception(
                        "TaskBudgetAlerter: log write failed for task %s, threshold %s",
                        task.id, t,
                    )
                    continue

                if recipients:
                    try:
                        self._send_alert(task, t, pct, recipients, planned, effective)
                    except Exception:
                        _logger.exception(
                            "TaskBudgetAlerter: email send failed for task %s",
                            task.id,
                        )

        self.write({"last_run": fields.Datetime.now()})
        return generated

    def _resolve_recipients(self, task):
        self.ensure_one()
        partners = self.env["res.partner"]

        if self.notify_assignee and task.user_ids:
            for user in task.user_ids:
                if user.partner_id and user.partner_id.email:
                    partners |= user.partner_id

        if (
            self.notify_manager
            and task.project_id
            and "user_id" in task.project_id._fields
            and task.project_id.user_id
            and task.project_id.user_id.partner_id
            and task.project_id.user_id.partner_id.email
        ):
            partners |= task.project_id.user_id.partner_id

        for user in self.extra_notify_user_ids:
            if user.partner_id and user.partner_id.email:
                partners |= user.partner_id
        return partners

    def _send_alert(self, task, threshold, pct, partners, planned, effective):
        self.ensure_one()
        body = _(
            "<p>Task <b>%(task)s</b> (project <b>%(project)s</b>) has "
            "crossed the <b>%(threshold)s%%</b> budget threshold.</p>"
            "<p><b>Planned:</b> %(planned).1fh<br/>"
            "<b>Logged:</b> %(logged).1fh<br/>"
            "<b>Current:</b> %(pct).1f%%</p>"
            "<p>Any extra hours logged will increase this. Consider "
            "re-estimating the task or flagging scope creep.</p>"
        ) % {
            "task": task.display_name or task.name or str(task.id),
            "project": (task.project_id.name if task.project_id else _("(no project)")),
            "threshold": threshold,
            "planned": planned,
            "logged": effective,
            "pct": pct,
        }
        self.env["mail.mail"].sudo().create({
            "subject": _("[Task Budget %s%%] %s") % (threshold, task.display_name or task.name),
            "body_html": body,
            "recipient_ids": [(6, 0, partners.ids)],
            "author_id": self.env.user.partner_id.id,
            "model": "project.task",
            "res_id": task.id,
        }).send()

        try:
            task.message_post(
                body=_(
                    "Task Budget Alerter [%(rule)s]: crossed %(t)s%% "
                    "threshold (%(pct).1f%%, %(logged).1f / %(planned).1fh)."
                ) % {
                    "rule": self.name,
                    "t": threshold,
                    "pct": pct,
                    "logged": effective,
                    "planned": planned,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            _logger.exception("TaskBudgetAlerter: chatter message failed")

    @api.model
    def _cron_scan(self):
        for rule in self.search([("active", "=", True)]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("TaskBudgetAlerter rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            generated = rule._run_one()
            if hasattr(rule, "message_post"):
                rule.message_post(
                    body=_("Task Budget manual run: %s alert(s) generated.") % generated
                )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Task Budget Scan"),
                "message": _("Done. See the log for details."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Alert Log"),
            "res_model": "cm_sa.task.budget.alert.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
