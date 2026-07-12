{
    "name": "Project Task Time-Budget Alerter",
    "version": "19.0.1.0.2",
    "summary": "Email alerts at 75 / 90 / 100% of project.task.planned_hours — assignee and manager. No approval ceremony, just receipts.",
    "description": """
Project Task Time-Budget Alerter
================================

Agency and services project managers discover tasks are 50% over
budget at invoice time, when the variance is already baked in and
impossible to recover. By then the client is unhappy and the
margin is gone.

Odoo core shows ``effective_hours`` and ``planned_hours`` on
``project.task`` but sends no threshold alert, so overruns surface
only on the monthly reporting pull.

**What this module adds:**

* Hourly cron computes each active task's budget percentage (``effective_hours / planned_hours``).
* Email alerts at 75 / 90 / 100% by default (thresholds configurable as a CSV of percentages).
* Notify the assignee, the project manager, or both per rule.
* Project scope (many-to-many) and excluded stages per rule.
* Deduped per (task, threshold): each task crosses each threshold exactly once per rule.
* Re-estimations that lower the planned hours can re-trigger later thresholds, that is intentional.
* Full audit log of every alert fired.

**Who benefits**

Project managers, delivery leads, and services operations teams at
SMB and mid-market agencies, consultancies, and professional
service firms.

**How it works**

Hourly cron that reads ``project.task`` only. No core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall. Pairs naturally with the rest of
the Cube Master audit / alert catalog.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Project",
    "depends": ["base", "mail", "project", "hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/task_budget_rule_views.xml",
        "views/task_budget_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
