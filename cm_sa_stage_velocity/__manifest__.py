{
    "name": "CRM Lead Stage Velocity Tracker",
    "version": "19.0.1.0.0",
    "summary": "Per-stage time-in-stage analytics on CRM leads. Pivot by salesperson × stage, 'stuck deals' smart filter, no per-rule setup.",
    "description": """
CRM Lead Stage Velocity Tracker
===============================

Sales managers want stage-velocity analytics: which stage is the
bottleneck, who has deals stuck more than N days, are some stages
inherently slower than others. Existing stage-history modules on
apps.odoo.com log the events; this one analyzes them.

Core's CRM kanban shows current stage but keeps no stage-history
rows, so "average days in stage" or "stuck deals over 30 days" are
not answerable without custom reporting.

**What this module adds:**

* ``cm_sa.crm.stage.history`` model: one row per (lead, stage entry) with entered_at, exited_at, and days_in_stage (computed).
* Automatic recording: wrapper on ``crm.lead.create`` and ``write(stage_id=...)`` writes history rows at registry load.
* No per-lead setup, install the module and every stage change is captured going forward.
* Pivot view by stage times salesperson, measure = average days_in_stage.
* Stuck Deals smart filter: leads whose current stage entry is older than a configurable threshold.
* Optional weekly digest email listing the top N stuck deals per team.

**Who benefits**

Sales managers, sales operations, and revenue analysts at SMB and
mid-market companies running structured CRM pipelines.

**How it works**

``_register_hook`` wrappers on ``crm.lead.create`` and stage-change
writes at registry load. No core-model inheritance of ``crm.lead``.
TransactionCase tested on Odoo 17, 18, and 19. Safe to install,
safe to uninstall. Historical lead stage history is not
back-filled, nothing to back-fill from in native Odoo.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["base", "mail", "crm"],
    "data": [
        "security/ir.model.access.csv",
        "views/crm_stage_history_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
