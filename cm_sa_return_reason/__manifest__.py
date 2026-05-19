{
    "name": "Customer Return Reason Enforcer",
    "version": "19.0.1.0.0",
    "summary": "Requires a typed reason on every customer return picking. Pivot by reason × product for warehouse QA analytics.",
    "description": """
Customer Return Reason Enforcer
===============================

Warehouse QA and operations managers need to know why customers
are returning goods: damage, wrong item, wrong size, customer
change of mind. Without that data, root-cause analytics are
impossible and recurring issues hide in plain sight.

Native Odoo has an optional Reason dropdown on the return wizard,
but nobody fills it and the data is unusable for analytics.

**What this module adds:**

* Typed reason is mandatory on every customer return picking.
* Configurable minimum length so reps cannot bypass with a single character.
* Optional reason category (damage, wrong-item, wrong-size, customer-change-of-mind, other).
* One-row-per-return audit log captures the reason, category, product, quantity, and source order.
* Pivot view by reason, product, and month ships out of the box.
* Works on every customer return, no per-warehouse configuration required.

**Who benefits**

Warehouse managers, QA teams, and operations leads at SMB and
mid-market companies with recurring return volume.

**How it works**

Wrapper on the return wizard plus a dedicated log model. No
core-model inheritance of ``stock.picking``. TransactionCase
tested on Odoo 17, 18, and 19. Safe to install, safe to uninstall.
Pairs naturally with our Reset-to-Draft Auditor and Change Reason
Guard for complete operations-audit coverage.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 40.00,
    "currency": "USD",
    "category": "Inventory",
    "depends": ["base", "mail", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/default_categories.xml",
        "views/return_reason_category_views.xml",
        "views/return_reason_config_views.xml",
        "views/return_reason_log_views.xml",
        "views/stock_return_picking_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
