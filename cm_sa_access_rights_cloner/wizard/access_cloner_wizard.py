import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccessClonerWizard(models.TransientModel):
    _name = "cm_sa.access.cloner.wizard"
    _description = "Access Rights Cloner Wizard"

    source_user_id = fields.Many2one(
        "res.users",
        string="Source user",
        required=True,
        help="User whose group membership will be copied to the targets.",
    )
    target_user_ids = fields.Many2many(
        "res.users",
        relation="cm_sa_access_cloner_target_rel",
        column1="wizard_id",
        column2="user_id",
        string="Target users",
        required=True,
        help="Users that will receive the source user's groups.",
    )
    mode = fields.Selection(
        [
            ("add", "Add (extend existing rights)"),
            ("replace", "Replace (mirror source exactly)"),
        ],
        default="add",
        required=True,
        help=(
            "Add: union of existing target groups and source groups. "
            "Replace: targets end up with exactly the source's groups — "
            "anything not on the source is removed."
        ),
    )

    preview_diff = fields.Text(
        string="Preview",
        compute="_compute_preview",
        readonly=True,
    )
    affected_groups_count = fields.Integer(
        string="Total group changes",
        compute="_compute_preview",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends("source_user_id", "target_user_ids", "mode")
    def _compute_preview(self):
        for wiz in self:
            if not wiz.source_user_id or not wiz.target_user_ids:
                wiz.preview_diff = _(
                    "Pick a source user and at least one target to see the diff."
                )
                wiz.affected_groups_count = 0
                continue

            source_groups = wiz.source_user_id.groups_id
            lines = []
            total_changes = 0

            for target in wiz.target_user_ids:
                target_groups = target.groups_id
                to_add = source_groups - target_groups
                to_remove = (
                    (target_groups - source_groups)
                    if wiz.mode == "replace"
                    else target.browse()
                )
                total_changes += len(to_add) + len(to_remove)

                lines.append(_("- %s") % target.display_name)
                if not to_add and not to_remove:
                    lines.append(_("    (no change)"))
                if to_add:
                    lines.append(_("    + groups to add (%s):") % len(to_add))
                    for grp in to_add:
                        lines.append("        + %s" % wiz._format_group(grp))
                if wiz.mode == "replace" and to_remove:
                    lines.append(_("    - groups to remove (%s):") % len(to_remove))
                    for grp in to_remove:
                        lines.append("        - %s" % wiz._format_group(grp))

            header = _(
                "%(targets)s target user(s), %(changes)s total group changes "
                "(mode: %(mode)s)\n"
            ) % {
                "targets": len(wiz.target_user_ids),
                "changes": total_changes,
                "mode": dict(wiz._fields["mode"].selection)[wiz.mode],
            }
            wiz.preview_diff = header + "\n".join(lines)
            wiz.affected_groups_count = total_changes

    @staticmethod
    def _format_group(group):
        """Render a res.groups for the diff: '[Privilege] Group name'.

        Odoo 19 uses ``privilege_id`` (not ``category_id``) on res.groups
        for the privilege grouping shown in the user form. We fall back
        gracefully if it isn't set.
        """
        privilege = ""
        if "privilege_id" in group._fields and group.privilege_id:
            privilege = "[%s] " % group.privilege_id.display_name
        return "%s%s" % (privilege, group.display_name or group.name)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_refresh_preview(self):
        """Trigger the compute by re-opening the wizard."""
        self.ensure_one()
        # Reading the field forces the compute on dependency change.
        self.invalidate_recordset(["preview_diff", "affected_groups_count"])
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_apply(self):
        self.ensure_one()
        if not self.source_user_id:
            raise UserError(_("Pick a source user."))
        if not self.target_user_ids:
            raise UserError(_("Pick at least one target user."))

        source = self.source_user_id
        source_group_ids = source.groups_id.ids
        total_added = 0
        total_removed = 0
        affected_users = 0

        for target in self.target_user_ids:
            if target == source:
                # Cloning a user to itself is a no-op; skip silently.
                continue

            before = target.groups_id
            if self.mode == "add":
                target.write({
                    "groups_id": [(4, gid) for gid in source_group_ids],
                })
            else:  # replace
                target.write({
                    "groups_id": [(6, 0, source_group_ids)],
                })
            after = target.groups_id

            added = after - before
            removed = before - after
            total_added += len(added)
            total_removed += len(removed)
            affected_users += 1

            mode_label = dict(self._fields["mode"].selection)[self.mode]
            target.message_post(
                body=_(
                    "Access rights cloned from <b>%(source)s</b> "
                    "(mode: %(mode)s). +%(added)s groups added, "
                    "-%(removed)s removed."
                ) % {
                    "source": source.display_name,
                    "mode": mode_label,
                    "added": len(added),
                    "removed": len(removed),
                },
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Access rights cloned"),
                "message": _(
                    "Updated %(users)s user(s): +%(added)s groups added, "
                    "-%(removed)s removed."
                ) % {
                    "users": affected_users,
                    "added": total_added,
                    "removed": total_removed,
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
