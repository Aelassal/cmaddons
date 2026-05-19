{
    "name": "Discount Audit Log",
    "version": "19.0.1.0.0",
    "summary": "Audit trail of every SO-line discount over a configurable threshold. No approval workflow — pure log + pivot.",
    "description": """
Discount Audit Log
==================

Sales managers want to see which reps give the biggest discounts,
without bolting on a heavy approval workflow. Existing paid modules
on apps.odoo.com (Sales Approval Enhancement, Sale Order Line
Discount Validation, OCA's free equivalent) all assume you want to
block the order until someone approves it.

Odoo core shows discount on each order line but offers no
aggregation, no threshold flag, and no historical report, so the
data stays locked in thousands of individual rows.

**What this module adds:**

* Set a threshold percentage (default 15%) in Settings.
* Every ``sale.order.line`` whose discount exceeds the threshold at create or write time writes one row to ``cm_sa.discount.audit.log``.
* Chatter note lands on the sale order naming the line, the discount percentage, and the threshold breached.
* List view plus pivot by salesperson times month ships out of the box.
* Optional inline reason field on the SO line; if filled, it is copied onto the log row. Not required, not blocking.
* No approval. No wizard. No blocking ``UserError``. Just the receipts.

**Who benefits**

Sales managers, finance controllers, and revenue analysts at SMB
and mid-market companies who want visibility without workflow
friction.

**How it works**

One log model plus a compute on ``sale.order.line``. No core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall. Pairs with ``cm_sa_margin_guard``
(which does block below-margin confirmations) for teams who want
both tools.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 40.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["base", "mail", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/discount_audit_config_views.xml",
        "views/discount_audit_log_views.xml",
        "views/sale_order_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
