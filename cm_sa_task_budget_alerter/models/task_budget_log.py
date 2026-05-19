from odoo import fields, models


class CmSaTaskBudgetAlertLog(models.Model):
    _name = "cm_sa.task.budget.alert.log"
    _description = "Task Budget Alert Log"
    _order = "create_date desc, id desc"

    rule_id = fields.Many2one(
        "cm_sa.task.budget.rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    task_id = fields.Many2one(
        "project.task",
        string="Task",
        ondelete="cascade",
        index=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        ondelete="set null",
        index=True,
    )
    threshold_pct = fields.Integer(
        string="Threshold %", required=True, index=True,
    )
    percent_at_alert = fields.Float(string="Actual % at Alert")
    planned_hours = fields.Float()
    effective_hours = fields.Float()

    def action_open_task(self):
        self.ensure_one()
        if not self.task_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.task",
            "res_id": self.task_id.id,
            "view_mode": "form",
            "target": "current",
        }
