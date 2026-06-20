{
    "name": "Negative Inventory Scanner",
    "version": "19.0.1.0.0",
    "summary": "Report (don't block) stock below zero — weekly per-location digest with aging. Visibility without workflow disruption.",
    "description": """
Negative Inventory Scanner
==========================

Existing "negative stock" apps on apps.odoo.com all prevent the
negative: they block pickings, break shipping workflows, and force
ops teams to fight the system. Odoo's forums are full of users
asking for the opposite: we don't want to block, we want to know.

Core shows negative quants in the inventory report but offers no
scheduled scan, no aging, and no digest email, so operations teams
either hand-audit weekly or discover problems at month-end.

**What this module adds:**

* Weekly cron scans ``stock.quant`` for quantity below zero.
* Results bundled per location plus product with aging (how many days the quant has been negative, based on ``write_date``).
* Snapshot plus detail log written to the database for audit.
* Digest email to the configured notify group on every run.
* On-demand Scan Now wizard triggers an immediate scan and opens the resulting snapshot.
* No blocking, no prevention, no workflow disruption, pure reporting.

**Who benefits**

Warehouse managers, inventory controllers, and operations leads at
SMB and mid-market companies who want visibility without breaking
the shipping floor.

**How it works**

Weekly cron plus a wizard-driven on-demand scan. No core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall. Pairs naturally with OCA's
``stock_no_negative`` when you want both, this one runs quietly in
the background, that one blocks at picking time.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Inventory",
    "depends": ["base", "mail", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/config_data.xml",
        "data/cron_data.xml",
        "wizard/scan_now_wizard_views.xml",
        "views/negative_stock_config_views.xml",
        "views/negative_stock_snapshot_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
