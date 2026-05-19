{
    "name": "Warehouse Transfer Turn-Around Alerter",
    "version": "19.0.1.0.0",
    "summary": "SLA alert on stock pickings that sit in flight longer than N days. Hourly cron + chatter stamp + email to warehouse manager.",
    "description": """
Warehouse Transfer Turn-Around Alerter
======================================

Warehouse managers lose visibility on transfers, internal moves
between locations, deliveries, receipts, that sit in progress for
days because nobody noticed. Odoo's ``stock.picking`` form shows
``scheduled_date`` but has no alerting on breach, so stalled
pickings only surface during month-end reconciliations.

Core has no picking-duration SLA, no aging escalation, and no
notify-group routing, so transfer hygiene is always a manual
backlog review.

**What this module adds:**

* Rule engine for picking-duration SLAs.
* Per rule: pick the operation type(s), optional source and destination location filter, max days between ``scheduled_date`` and now, notify group.
* Hourly cron flags pickings in ``assigned``, ``waiting``, or ``confirmed`` state that are overdue.
* First overdue detection writes a chatter note on the picking and emails the notify group.
* Aging buckets (5, 10, 20 days) trigger additional escalations so stale transfers never fall off the radar.
* Idempotent log keyed per (rule, picking, bucket) so "Run Now" is always safe and a restarted cron never double-emails.

**Who benefits**

Warehouse managers, operations leads, and supply-chain analysts at
SMB and mid-market companies with multi-location stock flow.

**How it works**

Hourly cron plus a (rule, source, keyed-date) audit log. No
core-model inheritance. TransactionCase tested on Odoo 17, 18, and
19. Safe to install, safe to uninstall.
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
        "data/cron_data.xml",
        "views/transfer_sla_rule_views.xml",
        "views/transfer_sla_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
