{
    "name": "Mandatory CRM Lost Reason",
    "version": "19.0.1.0.0",
    "summary": "Force sales reps to pick a Lost Reason and write a closing note when marking a lead lost.",
    "description": """
Mandatory CRM Lost Reason
=========================

Out of the box, Odoo lets a sales rep mark an opportunity as Lost
without picking a reason or leaving a comment. The result is the
same recurring complaint from sales managers: pipeline reports
full of "lost" deals with no explanation, no learning, and no
audit trail.

Core ships a Lost Reason dropdown but does not enforce it, and
does not require a closing note, so the field stays mostly empty.

**What this module adds:**

* Lost reason is mandatory. The Mark as Lost button refuses to close the wizard until a reason is selected.
* Closing note is mandatory with a configurable minimum length, so reps cannot bypass the rule with a single character.
* Both rules independently toggleable from Settings, CRM, CRM Lost Reason.
* Minimum note length configurable.
* Every successful "mark as lost" action posts a structured chatter message on the lead with the reason and the note.
* No UI redesign, only the native ``crm.lead.lost`` wizard is extended.

**Who benefits**

Sales managers, sales ops, and revenue analysts at SMB and
mid-market companies running structured CRM pipelines.

**How it works**

Pure server-side validation via ``UserError`` on the existing
``crm.lead.lost`` wizard. No JavaScript, no core-model surgery.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 40.00,
    "currency": "USD",
    "category": "Sales/CRM",
    "depends": ["crm"],
    "data": [
        "data/ir_config_parameter_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
