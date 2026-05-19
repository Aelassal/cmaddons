{
    "name": "Partner Master-Data Cascade",
    "version": "19.0.1.0.0",
    "summary": "Cascade parent-company address and VAT changes to child contacts, with preview and audit.",
    "description": """
Partner Master-Data Cascade
===========================

When a customer or vendor moves office, changes its VAT number, or
updates its billing email, the parent company record gets fixed,
but every one of its existing child contacts still holds the old
address. Your next invoice goes to the wrong street, your next tax
filing uses the wrong VAT.

Odoo core has no cascade primitive on ``res.partner``: parent
edits never flow down, and there is no preview of what would
change if they did.

**What this module adds:**

* One-click Cascade to contacts action on the parent partner form.
* Preview of every child contact that would be updated, showing old vs. new values.
* Untick individual children in the preview before applying.
* Children whose value differs from the old parent value are skipped by default (they were customized on purpose).
* Configurable field list: which fields trigger the cascade (street, VAT, phone, email, language, and so on).
* Every cascade writes a log row plus a chatter post on the parent and each child touched.

**Who benefits**

Master-data stewards, finance operations, and CRM admins at SMB
and mid-market companies with large multi-contact partner records.

**How it works**

Wizard-driven, no core-model inheritance. TransactionCase tested
on Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Contacts",
    "depends": ["base", "contacts", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/default_settings.xml",
        "views/cascade_setting_views.xml",
        "views/cascade_log_views.xml",
        "views/res_partner_views.xml",
        "wizard/cascade_wizard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
