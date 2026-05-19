{
    "name": "Bulk Product Media Drop",
    "version": "19.0.1.0.0",
    "summary": "Drag a folder of product images — auto-assign to products by SKU, with variant and gallery support.",
    "description": """
Bulk Product Media Drop
=======================

Uploading product photos one-by-one is the top time-waster for
e-commerce teams running Odoo. ZIP-based importers help a bit but
force you to rename files first, then re-zip, then upload, then
match by hand if anything is off.

Native Odoo ships no bulk image dropper, no fuzzy SKU matcher, and
no variant-aware upload path, so large catalog refreshes stay a
half-day job.

**What this module adds:**

* Drop a folder of images and match them to existing products automatically.
* Filenames matched against internal references, barcodes, and optionally product names.
* Suffix-based routing: ``SKU123.jpg`` is the main image, ``SKU123-2.jpg`` is gallery position 2, ``SKU123-red.jpg`` is the red variant, ``SKU123-red-L.jpg`` is red / L, ``SKU123-thumb.jpg`` is a thumbnail override.
* Fuzzy matching (Levenshtein ratio) with per-run threshold.
* Dry-run preview showing which files will land where, plus the unmatched list.
* Variant attribute resolution that finds the ``product.product`` for any attribute-value combo.

**Who benefits**

E-commerce managers, product catalog editors, and marketing ops
teams at SMB and mid-market retailers refreshing product imagery
seasonally.

**How it works**

Pure wizard on ``product.template`` / ``product.product``. No
core-model inheritance, no JS gymnastics. TransactionCase tested
on Odoo 17, 18, and 19. Safe to install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Sales/E-commerce",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/bulk_media_wizard_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
