{
    "name": "Quotation Chase",
    "version": "19.0.1.0.3",
    "summary": "Auto-remind customers about sent quotations on a schedule, stops on confirm or customer reply.",
    "description": """
Quotation Chase
===============

Sales reps spend hours every week chasing customers who never
replied to a sent quotation. Odoo core sends the quote once and
then goes silent; there is no built-in follow-up cadence, and reps
end up with sticky notes, calendar reminders, or nothing at all.

Core has no chase schedule on ``sale.order``, no auto-stop on
reply, and no per-schedule mail template, so every rep invents
their own workaround.

**What this module adds:**

* Define one or more chase schedules (e.g. nudge after 3, 7, and 14 days).
* Pick a schedule on the quotation, or set a system-wide default.
* Hourly cron sends the next chase email when its delay elapses.
* Each chase uses an editable mail template you control.
* Auto-stops when the quotation is confirmed, locked, or cancelled.
* Auto-stops when the user pauses the chase manually on the quotation.
* Auto-stops when the customer replies by email on the sale order's chatter (measured since the last chase was sent).
* Chatter post on every chase for a clean audit trail on the document itself.

**Who benefits**

Sales reps, account executives, and sales managers at SMB and
mid-market companies running outbound quote-driven sales motions.

**How it works**

Hourly cron plus chatter-based reply detection. No core-model
surgery. TransactionCase tested on Odoo 17, 18, and 19. Safe to
install, safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["sale", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "data/chase_schedule_data.xml",
        "data/cron_data.xml",
        "views/chase_schedule_views.xml",
        "views/sale_order_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
