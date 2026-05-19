{
    "name": "Field Change Reason Enforcer",
    "version": "19.0.1.0.0",
    "summary": "Force a categorized reason + note when configured fields are changed.",
    "description": """
Field Change Reason Enforcer
============================

Sensitive fields, customer credit limits, product prices, invoice
due dates, tax settings, should never be changed without a written
reason. Compliance teams need a clean list of who changed what,
when, and why.

Odoo core logs field changes in chatter when tracking is enabled,
but requires no reason, enforces no categorization, and offers no
reporting on the deltas.

**What this module adds:**

* Pick the field(s) you want guarded on any model.
* Pick the reason categories (Price correction, Credit override, Data cleanup, and so on).
* Optionally require a minimum-length note to stop single-character bypasses.
* Change with Reason action appears in the cog menu of the guarded record.
* Wizard captures the new value, category, and note; the write goes through only after submit.
* Every change logged with user, field, old value, new value, category, note, and timestamp.

**Who benefits**

Controllers, compliance officers, data stewards, and operations
managers at mid-market and enterprise companies tracking sensitive
master-data changes.

**How it works**

Pure wizards plus configurable server-action bindings. No
core-model inheritance, no JS gymnastics, no write-time
interception that breaks transactions. TransactionCase tested on
Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/reason_category_views.xml",
        "views/reason_rule_views.xml",
        "views/reason_log_views.xml",
        "wizard/reason_wizard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
