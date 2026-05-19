{
    "name": "Customer Payment Behavior Score",
    "version": "19.0.1.0.0",
    "summary": "A/B/C/D score per customer based on historical payment behavior — updated nightly.",
    "description": """
Customer Payment Behavior Score
===============================

Stock Odoo knows a customer's current balance but not whether they
are fast or slow, a stretcher or a partial payer. Two customers
can carry the same balance and be wildly different risks, and the
credit team has no built-in way to tell them apart.

Core has no historical payment scoring, no band assignment, and no
confirm-time block based on behavior, so credit decisions stay
driven by gut feel and manual Excel pulls.

**What this module adds:**

* A / B / C / D band per partner based on real reconciled payment history.
* A: pays on or near due date, no partials, no stretch. B: small drift, occasionally late. C: usually late, noticeable stretch. D: chronically late, heavy stretch, or partial-only.
* Nightly cron scans all partners with accounting activity in the configured window (default 90 days).
* Metrics computed: average days-late on reconciled customer invoices, partial-payment ratio, credit-limit stretch ratio, on-time streak.
* Weights and band cutoffs configurable.
* Scores, bands, and a JSON breakdown stored on the partner. Monthly snapshots appended so trends are traceable.
* Optional: block sale-order confirmation for band D customers unless the user is a system administrator.

**Who benefits**

Credit controllers, A/R managers, and CFOs at SMB, mid-market, and
enterprise companies with a recurring invoice volume.

**How it works**

Nightly cron computes behavior; optional confirm-time block uses a
safe ``_register_hook`` wrap on ``sale.order.action_confirm`` (no
core-model inheritance). TransactionCase tested on Odoo 17, 18,
and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail", "sale", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "data/config_data.xml",
        "views/payment_score_config_views.xml",
        "views/payment_score_snapshot_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
