{
    "name": "Config Parameter Change Auditor",
    "version": "19.0.1.0.0",
    "summary": "Zero-config audit trail for every ir.config_parameter change — with diff, chatter, and admin email alerts.",
    "description": """
Config Parameter Change Auditor
===============================

Security and compliance teams know someone changed a system
parameter, ``web.base.url``, ``auth.signup.allowed``, a payment
provider key, the mail catchall domain, but cannot easily see who
or when. OCA's ``auditlog`` tracks anything but requires per-model
rule setup; SMB admins install it, never configure it, and get no
audit trail.

Odoo core shows the current value of every ``ir.config_parameter``
but keeps no history, so changes are invisible after the fact.

**What this module adds:**

* Every write, create, and unlink on ``ir.config_parameter`` captured automatically with old value, new value, user, and timestamp.
* Pre-seeded watch list of security-critical keys (base URL, signup, API tokens, mail catchall, and so on).
* Keys on the watch list trigger an immediate email alert to the admin group on change.
* Keys outside the watch list still get logged, just without the alert.
* Weekly digest grouping recent changes for admins who want a lighter-touch review.
* Install-and-walk-away: zero rules to configure for full coverage.

**Who benefits**

IT admins, security officers, and compliance teams at SMB,
mid-market, and enterprise companies subject to change-control
audit.

**How it works**

Wrapper on ``ir.config_parameter`` write / create / unlink
registered at registry load. No core-model inheritance.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall. Pairs with our Reset-to-Draft Auditor and
Confirm-Time Field Guard for complete enterprise-audit coverage.
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
        "data/default_config.xml",
        "views/config_auditor_settings_views.xml",
        "views/config_change_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
