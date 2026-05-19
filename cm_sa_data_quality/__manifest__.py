{
    "name": "Data Quality Scanner",
    "version": "19.0.1.0.0",
    "summary": "Rule-based daily data-health scanner — required fields, formats, staleness, orphans.",
    "description": """
Data Quality Scanner
====================

Every Odoo database decays over time: partners without emails,
products with malformed SKUs, stale references pointing at deleted
records, required fields left blank at import time. Nobody notices
until a month-end report crashes or a shipment is flagged for
missing data.

Core has no data-health scanner, no configurable rule set, and no
recurring cron, so decay goes undetected until it hurts.

**What this module adds:**

* Required field rule: flags records where a chosen field is empty.
* Regex format rule: flags values that do not match a pattern.
* Value-in-list rule: flags values outside a fixed allow-list.
* Stale value rule: flags records whose field has not been touched for N days.
* Orphan reference rule: flags many2one fields pointing at non-existent targets (common after unsafe bulk deletes).
* Findings upserted (same finding = one row, ``last_seen`` updated), severity-tagged (info / warn / fail).
* Chatter post on first discovery only so recurring issues do not spam users, plus a weekly admin email summarizing the top offending rules.

**Who benefits**

Data stewards, operations managers, and IT admins at SMB and
mid-market companies running multi-team Odoo deployments.

**How it works**

Daily cron runs every active rule. No core-model inheritance, no
JS. TransactionCase tested on Odoo 17, 18, and 19. Safe to
install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/dq_rule_views.xml",
        "views/dq_finding_views.xml",
        "views/dq_scan_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
