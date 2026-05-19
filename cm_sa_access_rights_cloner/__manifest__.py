{
    "name": "Access Rights Cloner",
    "version": "19.0.1.0.0",
    "summary": "Copy a user's full permission set to one or more other users in seconds.",
    "description": """
Access Rights Cloner
====================

Onboarding a new hire who needs the same permissions as a peer, or
promoting someone and wanting to mirror their manager's access,
means walking through dozens of security groups on the user form.
Native Odoo has no "copy permissions" action, and doing it
group-by-group is slow and easy to get wrong on technical groups.

**What this module adds:**

* Wizard to pick a source user, one or many target users, and a mode.
* Add mode extends each target's current rights with the source's groups, preserving everything the targets already had.
* Replace mode makes each target's rights exactly equal to the source's, removing groups the source does not hold.
* Preview of every group that will be added or removed, per target, before you click Apply.
* Contextual server action on the Users list: Action, Clone access rights from this user.
* Chatter post on every target recording who was cloned from, in which mode, and how many groups changed.

**Who benefits**

IT admins, HR operations, and external Odoo consultants at SMB and
mid-market companies who onboard, promote, or offboard users on a
regular cadence.

**How it works**

Pure wizard + server action on ``res.users``. No core-model
inheritance, no JS gymnastics. Safe to install, safe to uninstall.
TransactionCase tested on Odoo 17, 18, and 19.
    """,
    "author": "cm.sa",
    "website": "https://cm.sa",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "category": "Administration",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/access_cloner_wizard_views.xml",
        "views/menus.xml",
        "data/server_action.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "development_status": 'Production/Stable',
    "maintainers": ['cm-sa'],
}
