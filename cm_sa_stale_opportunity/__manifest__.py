{
    "name": "Stale Opportunity Auto-Close",
    "version": "19.0.1.0.0",
    "summary": "Auto-close CRM opportunities untouched for N days with a lost reason and chatter audit. Warns the AE before the axe falls.",
    "description": """
Stale Opportunity Auto-Close
============================

Sales pipelines rot. Account executives do not close dead leads,
the forecast becomes fiction, and sales managers waste a day every
month hand-tagging dormant opportunities by the dozen.

Odoo core has no auto-close for stale opportunities, no warning
email before the close, and no per-team or per-owner rule, so
hygiene is always someone's unpaid side project.

**What this module adds:**

* Daily cron flags opportunities matching a rule (by stage, team, owner, or domain) whose activity has gone quiet for too long.
* Warning email to the owner N days before close, so nothing is ever silently axed.
* Closes everything still quiet past the deadline, marking the lead lost with a configurable reason.
* Logs every close with user, timestamp, and the triggering rule.
* Rule-per-team-or-stage configuration so different parts of the pipeline can have different hygiene rules.
* Sensible defaults ship preconfigured, audit-trail on by default.

**Who benefits**

Sales managers, revenue operations, and CRM admins at SMB and
mid-market companies running multi-team CRM pipelines.

**How it works**

Daily cron plus a per-close audit log. No core-model inheritance,
no Studio, no destructive button hiding in the UI. TransactionCase
tested on Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["base", "mail", "crm"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/stale_opportunity_rule_views.xml",
        "views/stale_opportunity_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
