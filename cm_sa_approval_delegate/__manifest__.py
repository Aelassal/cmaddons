{
    "name": "Out-of-Office Approval Delegator",
    "version": "19.0.1.0.1",
    "summary": "Vacation cover for activities and approvals — auto-reassign on start and reverse on return.",
    "description": """
Out-of-Office Approval Delegator
================================

When someone with approval duties goes on leave, their pending
activities and approval requests sit in a queue nobody is watching.
Work stalls until they return, or every approval gets escalated
manually one at a time.

Odoo core has no delegation primitive on the user model, so
vacation cover turns into ad-hoc chatter pings and manual
reassignments that are easy to forget to reverse.

**What this module adds:**

* Delegation tab on the user form: pick a delegate, start date, end date.
* Per-delegation scope: cover activities, approval requests, or both.
* Hourly cron reassigns all open activities and approval requests (if the Approvals module is installed) to the delegate on start, and reverses them on end.
* Per-item tracking so the revert is precise, items that were not originally owned by the delegator are never touched.
* Manual End delegation now button on the user form for early returns.
* Full delegation log showing every reassignment and revert.
* Soft dependency on the Approvals module, works without it.

**Who benefits**

Approvers, managers, and IT admins at SMB and mid-market
companies where approval queues block real work during leave.

**How it works**

Minimal extension of ``res.users`` (fields only). The cron drives
every reassignment. Safe to install, safe to uninstall.
TransactionCase tested on Odoo 17, 18, and 19.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Productivity",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
        "views/res_users_views.xml",
        "views/delegation_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
