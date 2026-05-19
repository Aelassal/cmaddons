{
    "name": "SO Margin Guard",
    "version": "19.0.1.0.0",
    "summary": "Block or warn on sale-order confirmation when gross margin falls below a configurable threshold — with per-group override and reason logging.",
    "description": """
SO Margin Guard
===============

Sales managers want a guardrail: "no salesperson confirms an
order below 10% margin without explicit sign-off". Native Odoo
shows margin on the form but does not block confirmation, and the
paid margin-alert modules on apps.odoo.com all bake in a single
threshold for a single model.

Core provides no per-model configuration, no Python-expression
formula, and no reason-logging override group, so margin policy
stays a Slack rule.

**What this module adds:**

* Rule engine: pick any model (``sale.order``, a custom quotation or contract model) and any method (``action_confirm``, a custom button).
* Margin formula as a Python expression against the record, default ``(record.amount_untaxed - record.margin_cost) / record.amount_untaxed * 100`` for ``sale.order``.
* Threshold percentage per rule.
* Override group: only members can confirm below-threshold orders, and they are prompted for a reason first.
* Every override logged to ``cm_sa.margin.override.log`` with user, record, threshold, computed margin, reason, and timestamp.
* Pivot view by user times month ships out of the box.

**Who benefits**

Sales managers, CFOs, and revenue operations teams at SMB and
mid-market companies who want margin discipline without a heavy
approval workflow.

**How it works**

``_register_hook`` wrapper at registry load, no core-model
inheritance. TransactionCase tested on Odoo 17, 18, and 19. Safe
to install, safe to uninstall. Pairs naturally with
``cm_sa_so_confirm_guard`` (required fields at confirm) and
``cm_sa_reset_auditor`` (reason on reset-to-draft).
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Sales",
    "depends": ["base", "mail", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/margin_override_wizard_views.xml",
        "views/margin_guard_rule_views.xml",
        "views/margin_override_log_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
