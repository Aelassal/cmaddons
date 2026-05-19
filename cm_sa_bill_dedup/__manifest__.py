{
    "name": "Duplicate Vendor Bill Warner",
    "version": "19.0.1.0.0",
    "summary": "Fuzzy-match incoming vendor bills against history to flag near-duplicates.",
    "description": """
Duplicate Vendor Bill Warner
============================

Paying the same vendor bill twice is one of the most common A/P
mistakes. The vendor resends it, the scan is a little different,
someone uploads both, and nobody notices until reconciliation.
Odoo's standard duplicate check only catches exact-reference
collisions.

Core has no fuzzy match, no amount tolerance, and no date-proximity
scoring, so most near-duplicates sail through.

**What this module adds:**

* Fuzzy duplicate detector on every draft and posted vendor bill.
* Match score (0 to 1) based on reference similarity, amount tolerance, and date proximity.
* Warning banner on the bill form above the configured threshold.
* Candidate list with direct links to each near-duplicate.
* Review log so resolved false positives stop appearing.
* All thresholds (score, amount tolerance, date tolerance, lookback window) configurable from Accounting, Configuration, Settings.

**Who benefits**

Accountants, A/P clerks, and controllers at SMB and mid-market
companies processing dozens to hundreds of vendor bills a week.

**How it works**

One computed field on ``account.move``, no other core-model
inheritance. No external dependencies. TransactionCase tested on
Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Accounting",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
        "views/dedup_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
