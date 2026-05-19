{
    "name": "Attachment Size Enforcer (Per-Model)",
    "version": "19.0.1.0.0",
    "summary": "Per-model max upload size on ir.attachment. Block oversize uploads with UserError. Optional bypass group.",
    "description": """
Attachment Size Enforcer (Per-Model)
====================================

Existing attachment-size-limit modules on apps.odoo.com are global
or per-user, one cap for the whole database, or one cap per user.
In practice a 200 MB CAD file on a ``sale.order`` is fine, but a
10 MB selfie on ``res.partner`` is a disaster. Different workflows
need different caps.

Odoo core has no per-model upload cap, so admins either pick an
over-broad global limit or leave the filestore to bloat.

**What this module adds:**

* Per rule: pick the Odoo model (``ir.model``), set the max size in MB, optionally pick a bypass group.
* Upload over the cap raises a ``UserError`` with a clear message naming the field, the file size, and the cap.
* Bypass group can override, with a chatter note on the target record and an optional reason.
* Rules enabled or disabled from the same settings list, no code changes required.
* Works across every model, from ``product.product`` images to ``res.partner`` business cards to ``mrp.bom`` drawings.

**Who benefits**

IT admins, system administrators, and operations managers at SMB
and mid-market companies trying to keep the filestore lean.

**How it works**

No core-model inheritance. ``_register_hook`` wraps
``ir.attachment.create`` at registry load. TransactionCase tested
on Odoo 17, 18, and 19. Safe to install, safe to uninstall. Pairs
well with our Filestore Orphan Sweeper, this one stops new bloat,
that one cleans up old bloat.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Administration",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/attachment_size_rule_views.xml",
        "views/attachment_size_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
