{
    "name": "Customer Credit Hold Manager",
    "version": "19.0.1.0.0",
    "summary": "One-click manual credit hold — blocks sales, purchase, and delivery confirmation.",
    "description": """
Customer Credit Hold Manager
============================

When a customer goes past due or a fraud concern lands in A/R, the
decision is usually "stop shipping and stop quoting until this is
resolved". Odoo's standard credit-limit field only warns, it does
not block, so orders keep flowing while A/R chases.

Core has no manual hold flag, no multi-document block (sale,
purchase, stock), and no release-date scheduling, so A/R teams
resort to sticky notes and direct calls to sales.

**What this module adds:**

* One-click credit-hold switch on any ``res.partner``.
* Blocks confirming sale orders where the customer, invoice-to, or ship-to is held.
* Blocks confirming purchase orders against a held vendor (for compliance holds).
* Blocks validating stock pickings against held partners.
* Reason, applied-by user, and expected release date captured on every hold.
* Blocked confirm attempts logged too, so A/R can see how often the hold is actually stopping work.
* Audit trail posted to chatter on both partner and document sides.

**Who benefits**

A/R clerks, credit controllers, and finance managers at SMB and
mid-market companies with recurring collection issues.

**How it works**

No JavaScript. All logic lives in ``_register_hook`` wrappers at
registry load, following the same pattern as our Confirm-Time
Field Guard app. TransactionCase tested on Odoo 17, 18, and 19.
Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Accounting",
    "depends": ["base", "sale", "purchase", "stock", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/credit_hold_log_views.xml",
        "wizard/credit_hold_wizard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
