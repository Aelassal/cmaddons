{
    "name": "Contract Renewal Pipeline Manager",
    "version": "19.0.1.0.0",
    "summary": "Auto-create pre-filled CRM opportunities N days before contracts / SOs expire — so no renewal is ever missed.",
    "description": """
Contract Renewal Pipeline Manager
=================================

Account executives with service-contract customers (not
subscription products, those are handled by Odoo Subscriptions)
miss renewal windows because there is no built-in auto-prompt.
Odoo Subscriptions renews the subscription record itself; it does
not create a CRM opportunity for the AE to engage with. Generic
contracts, fixed-term service orders, and custom contract models
do not even get that far.

Core has no model-agnostic renewal watcher and no auto-creation of
``crm.lead`` rows with type ``opportunity``, so renewals rely on
memory.

**What this module adds:**

* Renewal rule: pick any model (``sale.order``, ``account.move``, a custom contract model) and the end-date field to watch.
* Set lead time in days (e.g. "open a pipeline opportunity 60 days before end-date").
* Pick the sales team and default pipeline stage for the new opportunity.
* Optionally pick a quotation template so the AE can send the renewal quote in one click.
* Optionally restrict to a subset with an extra domain.
* Daily cron creates each ``crm.lead`` with ``type='opportunity'``, name prefilled "Renew: {customer}, {subject}", partner and sales team set, and expected revenue prefilled from the source record when possible.
* Idempotent log in ``cm_sa.renewal.log`` keyed per (rule, source) so the same record never generates two opportunities.

**Who benefits**

Account executives, customer success managers, and sales
operations teams at SMB and mid-market companies with recurring
service engagements.

**How it works**

Daily cron plus a (rule, source, keyed-date) log. No core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["base", "mail", "crm", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/renewal_rule_views.xml",
        "views/renewal_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
