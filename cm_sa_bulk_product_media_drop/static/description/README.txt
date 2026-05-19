Files required for Odoo App Store submission
==============================================

index.html               — written, describes the module on apps.odoo.com.

Binary assets to replace before publishing:

icon.png                 — 140 x 140 PNG, square. Currently an empty
                           placeholder. Must be replaced.

banner.png               — top banner image, 1280 x 720 PNG recommended
                           (landscape). Referenced by index.html. Not yet
                           created.

screenshot_wizard.png    — a real screenshot of the wizard step 1
                           (captured from the live install).

screenshot_preview.png   — not yet created. Suggested content: the wizard
                           on the Preview step, showing the JSON match plan
                           with a mix of matched + unmatched files.

Checklist before submission
===========================

1. Replace icon.png.
2. Create banner.png.
3. Produce the missing screenshot above (preview step).
4. Double-check the manifest:
   - author, website, license (OPL-1), price, currency — all correct.
5. Smoke-install on a fresh Odoo 17 / 18 / 19 DB (see
   /home/odoo/odoo-local/ for the 19.0 test env).
6. Zip the module folder and upload via the "Publish" button on
   apps.odoo.com.
