{
    "name": "Approval Escalation Engine",
    "version": "19.0.1.0.0",
    "summary": "Auto-escalate pending approvals, POs, expenses, and leaves when approvers sit on them too long.",
    "description": """
Approval Escalation Engine
==========================

Pending records getting stuck on an approver's desk is one of the
most common Odoo pain points. If the approver is on leave, sick,
or just slow, the record waits silently and nobody notices until
somebody complains.

Odoo core has no auto-escalation on purchase orders, expense
reports, leaves, or approval requests. Chatter activities can
remind the approver, but there is no built-in way to reassign to
a manager or a named fallback after N hours.

**What this module adds:**

* Rule engine per model: pick the target model, state, and owner field.
* After N hours without action, send a reminder activity or email to the approver.
* After another N hours, reassign to the approver's manager.
* After another N hours, escalate to a named recipient (e.g. CFO).
* Out-of-the-box rules for purchase orders, expense reports, time off / leave requests, and approval requests.
* Custom rules can target any model with a state and an owner field.
* Full audit log of every escalation, who was reassigned, when, and why.

**Who benefits**

Approvers, controllers, finance managers, and operations leads at
mid-market and enterprise companies where approval SLAs matter.

**How it works**

Cron-driven rule evaluation, no core-model inheritance. Every
escalation writes to the audit log and posts to chatter.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 59.00,
    "currency": "USD",
    "category": "Human Resources/Approvals",
    "depends": ["mail", "base", "hr"],
    "data": [
        "security/escalation_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "data/cron_data.xml",
        "views/escalation_rule_views.xml",
        "views/escalation_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
