{
    "name": "Dormant User Auto-Disabler",
    "version": "19.0.1.0.0",
    "summary": "Auto-disable Odoo users inactive for N days — with warning email first, ROI dashboard, one-click reactivate.",
    "description": """
Dormant User Auto-Disabler
==========================

Odoo Enterprise bills per active user. Employees leave, change
roles, or go on long leave, and nobody remembers to deactivate
them. At month-end the license bill is 20% too high, and nobody
can quickly tell which users are actually dormant.

Core has no login-date-based auto-disable, no warning email before
archive, and no ROI reporting on reclaimed seats.

**What this module adds:**

* Daily cron finds users whose ``login_date`` is older than a configurable threshold (default 90 days).
* Admin and configurable "always-active" groups always excluded from the sweep.
* Warning email to the user and the admin group N days before disable (default 7) so nothing is silently axed.
* Users past the deadline archived automatically; every action logged with user, days-inactive, and timestamp.
* ROI dashboard on the settings form: "5 users archived this month x $30/user = $150 saved".
* One-click Reactivate on any log row restores the user.

**Who benefits**

IT admins, HR operations, and finance controllers at mid-market
and enterprise companies paying per-user Odoo licensing.

**How it works**

Daily cron evaluates every active user. No core-model inheritance.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Administration",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/dormant_config_views.xml",
        "views/dormant_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
