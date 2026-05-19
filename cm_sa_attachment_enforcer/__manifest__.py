{
    "name": "Invoice Attachment Enforcer",
    "version": "19.0.1.0.0",
    "summary": "Block account.move posting when required attachments are missing. Per-journal rules, bypass group with reason wizard, full audit log.",
    "description": """
Invoice Attachment Enforcer
===========================

Controllers and auditors want every posted vendor bill to carry
its original PDF, and every customer invoice to carry its approval
email. Odoo posts ``account.move`` records without attachments
silently, and at audit time half the attachments are missing with
no way to find which ones.

Native Odoo has no per-journal attachment requirement and no bypass
workflow, so finance teams either nag manually or accept the gap.

**What this module adds:**

* Per-rule config: pick journal types, specific journals, minimum attachment count, and allowed mime-types.
* Block ``account.move.action_post`` when the rule's minimum is not met, with a clear error message.
* Bypass group: managers can post without attachment after filling a reason wizard.
* Every bypass logged with user, record, reason, and timestamp.
* Audit trail posted to the document's chatter on every block and bypass.
* Works on customer invoices, vendor bills, and any journal type you configure.

**Who benefits**

Controllers, accountants, and internal auditors at mid-market and
enterprise companies subject to document-retention audit.

**How it works**

No core-model inheritance. The wrapper installs via
``_register_hook`` at registry load and wraps
``account.move.action_post``. Safe to install, safe to uninstall.
TransactionCase tested on Odoo 17, 18, and 19. Pairs with our
Confirm-Time Field Guard and Reset-to-Draft Auditor for complete
enterprise-audit coverage.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Accounting",
    "depends": ["base", "mail", "account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/attachment_bypass_wizard_views.xml",
        "views/attachment_rule_views.xml",
        "views/attachment_bypass_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
