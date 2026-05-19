{
    "name": "Confirm-Time Field Guard",
    "version": "19.0.1.0.0",
    "summary": "Make any field conditionally required at the confirm/post/validate button — without Studio.",
    "description": """
Confirm-Time Field Guard
========================

Some fields only matter at confirm time: a customer PO number on a
sale order, an internal reference on a vendor bill, a destination
location on a stock picking. Marking them ``required=True`` on the
model is too aggressive, it blocks drafts, imports, and
quotations.

Odoo core offers no conditional-required primitive, and Studio's
approach requires writing onchange code per model, which breaks on
the next upgrade.

**What this module adds:**

* Per model: declare which action method to guard (``action_confirm``, ``action_post``, ``button_validate``, or any custom button).
* Declare the fields that must be filled at that action.
* Optional domain so the rule only applies to a subset (e.g. orders above a threshold).
* Custom error message per rule.
* Multiple rules on the same method grouped into a single wrapper that runs them in order.
* No Studio required, rules are pure data you can ship between databases.

**Who benefits**

Sales ops, accounting teams, warehouse managers, and operations
leads at SMB and mid-market companies who need conditional field
discipline at key workflow transitions.

**How it works**

``_register_hook`` wraps the configured methods on the model class
itself at registry load. No core-model inheritance, no
monkey-patching of imported modules. TransactionCase tested on
Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/confirm_guard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
