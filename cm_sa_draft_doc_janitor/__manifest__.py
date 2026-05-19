{
    "name": "Draft Document Janitor",
    "version": "19.0.1.0.0",
    "summary": "Auto-cancel, archive, or notify on stale draft invoices, RFQs, quotations, and pickings.",
    "description": """
Draft Document Janitor
======================

Stale draft documents pile up in every Odoo database: RFQs nobody
confirmed, quotations that ghosted, draft invoices left half-done,
pickings created and forgotten. They clutter list views, distort
reports, and hide the real pipeline from managers.

Core has no auto-cleanup for stale drafts; teams either hand-clean
quarterly or let the backlog grow indefinitely.

**What this module adds:**

* Define a rule per model: pick the model, the state value that means "draft", and how old (in days) is too old.
* Pick an action per rule: notify the owner, auto-cancel, or auto-archive.
* Out-of-the-box rules for sale orders / quotations, purchase orders / RFQs, customer and vendor invoices, and stock pickings.
* Daily cron runs every active rule, processing every matching record.
* Every action logged and posted to the document's chatter so the audit trail is clear.
* Per-model exclusion domains so specific records can opt out.

**Who benefits**

Operations managers, sales ops, and finance teams at SMB and
mid-market companies who want clean list views without manual
cleanup passes.

**How it works**

Daily cron runs every active rule. No core-model inheritance.
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
        "views/janitor_rule_views.xml",
        "views/janitor_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
