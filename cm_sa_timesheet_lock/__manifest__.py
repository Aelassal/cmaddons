{
    "name": "Timesheet Back-Dating Limit (Rolling Window)",
    "version": "19.0.1.2.0",
    "summary": "Block timesheet entries more than N days old — rolling window that auto-advances daily. Bypass group with reason.",
    "description": """
Timesheet Back-Dating Limit (Rolling Window)
============================================

Services project managers and compliance teams need to stop
retroactive timesheet edits, an employee logging hours for "three
months ago" to clear a client budget variance, or backfilling
dates to hit a deadline. Existing lock modules use absolute lock
dates (lock everything before Dec 31); what teams actually want is
a rolling window.

Odoo core offers no rolling-window timesheet lock and no bypass
group, so the only options are fixed-date locks (which need admin
maintenance every period) or no lock at all.

**What this module adds:**

* Per rule: apply to members of selected groups (or all users if empty).
* Max days back integer (default 14).
* Creating or writing an ``account.analytic.line`` with a date older than today minus N raises a ``UserError``.
* Bypass group overrides with a chatter log and audit-log row.
* Window advances by itself every day, no admin calendar ceremony required.
* Clear error message names the date and the earliest allowed date.

**Who benefits**

Project managers, services operations, and compliance teams at SMB
and mid-market services firms that bill clients by time.

**How it works**

``_register_hook`` wrapper on ``account.analytic.line`` create /
write at registry load. No core-model inheritance.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall. Pairs naturally with our Project Task Time
Budget Alerter and Reset-to-Draft Auditor for complete
project-time governance.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Project",
    "depends": ["base", "web", "mail", "hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "views/timesheet_lock_rule_views.xml",
        "views/timesheet_lock_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "assets": {
        "web.assets_backend": [
            "cm_sa_timesheet_lock/static/src/js/bypass_reason_dialog.js",
            "cm_sa_timesheet_lock/static/src/xml/bypass_reason_dialog.xml",
        ],
    },
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
