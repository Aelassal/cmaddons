{
    "name": "Filestore Orphan Sweeper",
    "version": "19.0.1.0.0",
    "summary": "Find and delete filestore files with no matching ir.attachment row.",
    "description": """
Filestore Orphan Sweeper
========================

Over time Odoo's filestore accumulates orphan files: binaries that
no longer have a corresponding ``ir.attachment`` row. They consume
disk, inflate backups, and don't serve any user content. Odoo's
built-in garbage collector catches some of them, but many leak past.

There is no admin-friendly tool to audit the filestore, preview
orphans, or reclaim space without hand-crafted shell scripts.

**What this module adds:**

* Scan the active database's filestore and cross-reference every file against ``ir.attachment.store_fname``.
* Preview orphans: count, total size, sample filenames.
* Delete with confirmation; every run logged (scanned count, orphan count, size, deleted count, dry-run flag, user, timestamps).
* Safety rail: files younger than 24 hours are never deleted (they may still be mid-upload).
* System-admin-only menu (``base.group_system``), no accidental access for regular users.
* Full history of every sweep so storage reclaim is reportable.

**Who benefits**

System administrators, DevOps, and IT operations at mid-market and
enterprise companies with large filestore footprints.

**How it works**

Manual wizard plus a persistent log. No core-model inheritance.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall. Pairs with our Attachment Size Enforcer, that
one stops new bloat, this one cleans up old bloat.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Administration",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/sweep_wizard_views.xml",
        "views/sweep_run_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
