{
    "name": "Vendor Performance Scorecard",
    "version": "19.0.1.0.0",
    "summary": "Monthly A/B/C/D scorecard per vendor — on-time receipts, price variance, bill disputes.",
    "description": """
Vendor Performance Scorecard
============================

Purchasing teams need to know which vendors ship on time, hold
prices steady, and send clean bills, and which ones do not. Most
ERPs hide that data in spreadsheets, and Odoo's vendor form shows
raw PO history without any aggregation.

Core has no vendor scorecard, no weighted score, and no monthly
snapshot, so vendor reviews rely on gut feel plus whichever
spreadsheet the buyer maintains.

**What this module adds:**

* Monthly cron computes, for every vendor with activity in the window, on-time percentage (receipts received on or before ``date_planned``).
* Average days late on the late ones.
* Price variance percentage (this month's vendor-product price vs. the trailing 6-month average).
* Bill-dispute count (vendor bills reset to draft or corrected after posting).
* Metrics weighted into a 0-to-100 score and mapped to an A / B / C / D band.
* Snapshots stored per period so trends show up in a pivot or graph.
* Recompute Now button on the vendor form for an up-to-the-minute score on demand.

**Who benefits**

Purchasing managers, procurement analysts, and operations leads at
SMB and mid-market companies with a recurring vendor base.

**How it works**

Monthly cron plus a per-period snapshot model. No core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Purchases",
    "depends": ["base", "mail", "purchase", "stock", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "data/config_data.xml",
        "views/vendor_scorecard_config_views.xml",
        "views/vendor_scorecard_snapshot_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
