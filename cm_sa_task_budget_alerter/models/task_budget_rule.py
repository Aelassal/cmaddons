import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CmSaTaskBudgetRule(models.Model):
    _name = "cm_sa.task.budget.rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Task Time-Budget Alert Rule"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    thresholds_csv = fields.Char(
        string="Thresholds (%)",
        default="75,90,100",
        required=True,
        help="Comma-separated percentages. An alert is emailed the first "
             "time a task's (effective / planned) hours crosses each "
             "threshold. Example: '75,90,100'. Only positive integers.",
    )
    notify_assignee = fields.Boolean(
        default=True,
        help="Email the task's assignee (user_ids) on threshold crossing.",
    )
    notify_manager = fields.Boolean(
        default=True,
        help="Email the project manager (user_id on project.project) on "
             "threshold crossing.",
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
        help="Ignore tasks with planned_hours below this value. Filters "
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
                    "integers (e.g. '75,90,100'): %s"
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
        """Return a sorted list of int thresholds."""
        self.ensure_one()
        if not self.thresholds_csv:
            return []
        parts = [p.strip() for p in re.split(r"[,\s]+", self.thresholds_csv) if p.strip()]
        return sorted({int(p) for p in parts})

    def _project_domain(self):
        self.ensure_one()
        return [("id", "in", self.project_ids.ids)] if self.project_ids else []

    def _candidate_domain(self):
        self.ensure_one()
        domain = [
            ("planned_hours", ">=", self.min_planned_hours),
            ("planned_hours", ">", 0),
        ]
        if self.project_ids:
            domain += [("project_id", "in", self.project_ids.ids)]
        if self.exclude_stage_ids:
            domain += [("stage_id", "not in", self.exclude_stage_ids.ids)]
        return domain

    def _compute_percent(self, task):
        planned = task.planned_hours or 0.0
        if planned <= 0:
            return 0.0
        logged = task.effective_hours or 0.0
        return logged / planned * 100.0

    def _run_one(self):
        self.ensure_one()
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

        sent = 0
        for task in tasks:
            pct = self._compute_percent(task)
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
                        "planned_hours": task.planned_hours or 0.0,
                        "effective_hours": task.effective_hours or 0.0,
                    })
                except Exception:
                    _logger.exception(
                        "TaskBudgetAlerter: log write failed for task %s, threshold %s",
                        task.id, t,
                    )
                    continue
                if recipients:
                    try:
                        self._send_alert(task, t, pct, recipients)
                        sent += 1
                    except Exception:
                        _logger.exception(
                            "TaskBudgetAlerter: email send failed for task %s",
                            task.id,
                        )

        self.write({"last_run": fields.Datetime.now()})
        return sent

    def _resolve_recipients(self, task):
        self.ensure_one()
        partners = self.env["res.partner"]
        if self.notify_assignee and task.user_ids:
            for u in task.user_ids:
                if u.partner_id:
                    partners |= u.partner_id
        if self.notify_manager and task.project_id and task.project_id.user_id:
            if task.project_id.user_id.partner_id:
                partners |= task.project_id.user_id.partner_id
        for u in self.extra_notify_user_ids:
            if u.partner_id:
                partners |= u.partner_id
        return partners

    def _send_alert(self, task, threshold, pct, partners):
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
            "planned": task.planned_hours or 0.0,
            "logged": task.effective_hours or 0.0,
            "pct": pct,
        }
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Task Budget %s%%] %s") % (threshold, task.display_name or task.name),
                "body_html": body,
                "recipient_ids": [(6, 0, partners.ids)],
                "author_id": self.env.user.partner_id.id,
                "model": "project.task",
                "res_id": task.id,
            }).send()
        except Exception:
            _logger.exception("TaskBudgetAlerter: mail send failed")
        try:
            task.message_post(
                body=_(
                    "Task Budget Alerter [%(rule)s]: crossed <b>%(t)s%%</b> "
                    "threshold (%(pct).1f%%, %(logged).1f / %(planned).1fh)."
                ) % {
                    "rule": self.name,
                    "t": threshold,
                    "pct": pct,
                    "logged": task.effective_hours or 0.0,
                    "planned": task.planned_hours or 0.0,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass

    @api.model
    def _cron_scan(self):
        for rule in self.search([]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("TaskBudgetAlerter rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            sent = rule._run_one()
            if hasattr(rule, "message_post"):
                rule.message_post(
                    body=_("Task Budget manual run: %s alert(s) emailed.") % sent
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
