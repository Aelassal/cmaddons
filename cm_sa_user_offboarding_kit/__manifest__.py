{
    "name": "User Offboarding Kit",
    "version": "19.0.1.0.3",
    "summary": "Schedule user deactivation dates, auto-archive dormant users, reclaim Enterprise seats.",
    "description": """
User Offboarding Kit
====================

When an employee leaves, reclaiming their Enterprise seat, revoking
their access, and cleaning up their audit trail takes a surprising
number of clicks, and easy steps get missed. Meanwhile dormant
accounts keep consuming licenses and keep carrying access they no
longer need.

Odoo core has no scheduled deactivation, no dormant-user list, and
no bulk offboarding wizard, so HR ops and IT run their own
checklists and hope nothing slips.

**What this module adds:**

* Schedule a deactivation date and reason on any user; a daily cron archives them on the date you set and posts the reason to chatter.
* Weekly cron flags users that have not logged in for N days (default 90) for review in a dedicated Dormant Users list.
* Bulk-archive dormant users from a wizard with a single shared reason, written to chatter on every archived account.
* System users (admin, public, portal, __system) always skipped.
* Every archive logged with user, reason, date, and source (scheduled / dormant / bulk).
* Reactivate is always one click from the user form.

**Who benefits**

IT admins, HR operations, and finance controllers at mid-market
and enterprise companies paying per-user Odoo Enterprise licensing.

**How it works**

Two stored fields on ``res.users`` and two crons (daily archive,
weekly dormant review). No deeper core-model surgery.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Administration",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "data/cron_data.xml",
        "wizard/dormant_archive_wizard_views.xml",
        "views/res_users_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
