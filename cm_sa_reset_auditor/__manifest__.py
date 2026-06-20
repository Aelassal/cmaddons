{
    "name": "Reset-to-Draft Auditor",
    "version": "19.0.1.0.0",
    "summary": "Require a reason, restrict to a group, and log every reset-to-draft on SOs, invoices, POs, pickings — any model.",
    "description": """
Reset-to-Draft Auditor
======================

Controllers know that sale orders and invoices get reset to draft
and quietly edited, but cannot easily find out who, when, or why.
Odoo logs the state change in chatter but does not require a
reason, does not restrict the button to privileged users, and does
not produce a report.

Core has no gate on reset-to-draft, so the audit trail has a hole
exactly where auditors look hardest.

**What this module adds:**

* Wrap the reset-to-draft method on any model at registry load.
* Per rule, configure the model (``sale.order``, ``account.move``, ``purchase.order``, ``stock.picking``, a custom model).
* Configure the method being wrapped (default ``action_draft``).
* Require a reason: click Reset, the wizard asks why, the write only happens on submit.
* Optional required group: only members can reset.
* Optional domain so the rule only applies to a subset.
* Every reset writes a ``cm_sa.reset_audit.log`` row with user, reason, timestamp, and a link back to the record.
* Dashboard pivots by user, model, week, and rule.

**Who benefits**

Controllers, internal auditors, and compliance officers at
mid-market and enterprise companies subject to document-audit
reviews.

**How it works**

``_register_hook`` wrapper at registry load, TransientModel
wizard, and an idempotent audit log. No core-model inheritance, no
JS. TransactionCase tested on Odoo 17, 18, and 19. Safe to
install, safe to uninstall.
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
        "wizard/reset_reason_wizard_views.xml",
        "views/reset_audit_rule_views.xml",
        "views/reset_audit_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
