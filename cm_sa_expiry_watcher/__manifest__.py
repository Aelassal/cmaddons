{
    "name": "Any-Model Expiry Alerter",
    "version": "19.0.1.0.0",
    "summary": "Watch any date/datetime field on any model and alert before expiry.",
    "description": """
Any-Model Expiry Alerter
========================

Contracts, warranties, certifications, insurance policies,
passports, NDAs, employee visas, equipment calibrations, every
Odoo database stores dozens of dated things that silently expire.
When one of them lapses the consequences range from annoying to
catastrophic.

Odoo core has no generic expiry watcher, so teams either
hand-build activities on each model or rely on calendar reminders
that rot with the people who set them.

**What this module adds:**

* Configure a rule in one form: pick the model and the ``date`` / ``datetime`` field to watch.
* Set the lead time in days (e.g. "alert 30 days before").
* Pick users to notify and an optional email template.
* Optionally restrict to a subset with an extra domain.
* Daily cron scans every active rule and, for each record about to expire, posts to the record's chatter and emails the notifiers.
* Idempotent log keyed on ``(rule, res_model, res_id, date)`` so the same expiry never pings twice.

**Who benefits**

HR operations, compliance officers, facilities managers, and
account managers at SMB, mid-market, and enterprise companies
tracking time-sensitive records.

**How it works**

Daily cron plus a (rule, source, keyed-date) audit log. No
core-model inheritance. TransactionCase tested on Odoo 17, 18, and
19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/expiry_rule_views.xml",
        "views/expiry_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
