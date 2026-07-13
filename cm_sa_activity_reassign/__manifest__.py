{
    "name": "Bulk Activity Reassignment",
    "version": "19.0.1.0.1",
    "summary": "Reassign hundreds of mail.activity records from one user to another in one click.",
    "description": """
Bulk Activity Reassignment
==========================

When an employee leaves, changes role, or goes on extended leave,
their open activities pile up and block every workflow they
touched, sales follow-ups, accounting reviews, HR tasks, project
to-dos. Reassigning them one at a time through the chatter takes
hours; the SQL shortcut skips the audit trail entirely.

Odoo core lets you reassign activities individually but ships no
bulk transfer tool, so offboarding day always turns into
hand-clicking.

**What this module adds:**

* Wizard to transfer every ``mail.activity`` from one user to another in one shot.
* Optional filters on model, activity type, and deadline range.
* "Overdue only" toggle for the offboarding-day cleanup pass.
* Optional new deadline applied to every reassigned activity.
* Live preview count so you see how many activities match before pressing Apply.
* Contextual button on the user form: Reassign their activities, prefilled with that user as source.
* Chatter post on every parent record that inherits ``mail.thread``, preserving the audit trail.

**Who benefits**

IT admins, HR operations, and team leads at SMB and mid-market
companies with fluid role assignments and regular offboarding.

**How it works**

The wizard is a ``TransientModel`` with no core-model inheritance.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/activity_reassign_wizard_views.xml",
        "data/server_actions.xml",
        "views/menus.xml",
        "views/res_users_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
