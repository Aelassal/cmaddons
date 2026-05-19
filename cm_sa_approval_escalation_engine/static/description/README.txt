Files required for Odoo App Store submission
==============================================

index.html               — written, describes the module on apps.odoo.com.

Binary assets to replace before publishing:

icon.png                 — 140 x 140 PNG, square. Currently an empty
                           placeholder. Must be replaced.

banner.png               — top banner image, 1280 x 720 PNG recommended
                           (landscape). Referenced by index.html. Not yet
                           created.

screenshot_rule_form.png — a real screenshot of the rule form
                           (1400 x 900, captured from the live install).
                           Swap with your own polished version if you want.

screenshot_step_actions.png — not yet created. Suggested content: the
                           escalation_step list with different actions
                           (notify, escalate_manager, escalate_user).

screenshot_log.png       — not yet created. Suggested content: the
                           "Escalation Log" list view with several entries
                           after the cron has fired.

Checklist before submission
===========================

1. Replace icon.png.
2. Create banner.png.
3. Produce the two missing screenshots above.
4. Double-check the manifest:
   - author, website, license (OPL-1), price, currency — all correct.
5. Smoke-install on a fresh Odoo 17 / 18 / 19 DB (see
   /home/odoo/odoo-local/ for the 19.0 test env).
6. Zip the module folder and upload via the "Publish" button on
   apps.odoo.com.
