import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CmSaCascadeWizard(models.TransientModel):
    _name = "cm_sa.cascade.wizard"
    _description = "Partner Cascade Wizard"

    partner_id = fields.Many2one(
        "res.partner",
        string="Parent Partner",
        required=True,
        domain="[('is_company', '=', True)]",
    )
    affected_partner_ids = fields.Many2many(
        "res.partner",
        "cm_sa_cascade_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Children to Update",
    )
    changes_preview = fields.Text(
        compute="_compute_preview",
        readonly=True,
    )
    summary = fields.Char(
        compute="_compute_preview",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Defaults / preview
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_id = res.get("partner_id") or self.env.context.get("default_partner_id")
        if partner_id:
            parent = self.env["res.partner"].browse(partner_id)
            res["affected_partner_ids"] = [(6, 0, parent.child_ids.ids)]
        return res

    @api.depends("partner_id", "affected_partner_ids")
    def _compute_preview(self):
        Setting = self.env["cm_sa.cascade.setting"].sudo()
        watched = Setting._watched_field_names()
        for wiz in self:
            if not wiz.partner_id or not watched:
                wiz.changes_preview = _(
                    "Configure watched fields in Settings first, then reopen."
                )
                wiz.summary = _("0 fields watched")
                continue
            parent = wiz.partner_id
            lines = [_("Cascading from: %s") % parent.display_name, ""]
            for fname in watched:
                label = parent._fields[fname].string if fname in parent._fields else fname
                value = parent[fname]
                display = value.display_name if hasattr(value, "display_name") and value else (value or "—")
                lines.append("  %s: %s" % (label, display))
            lines.append("")
            lines.append(_("Will update these child contacts:"))
            for child in wiz.affected_partner_ids:
                lines.append(_("  - %s") % child.display_name)
            wiz.changes_preview = "\n".join(lines)
            wiz.summary = _(
                "%(fields)s watched field(s), %(children)s child(ren)"
            ) % {
                "fields": len(watched),
                "children": len(wiz.affected_partner_ids),
            }

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No parent partner selected."))
        if not self.affected_partner_ids:
            raise UserError(_("No child contacts selected."))

        Setting = self.env["cm_sa.cascade.setting"].sudo()
        watched = Setting._watched_field_names()
        if not watched:
            raise UserError(_(
                "No watched fields configured. Open "
                "Contacts → Cascade → Settings to pick them."
            ))

        parent = self.partner_id
        vals = {}
        snapshot = {}
        for fname in watched:
            field = parent._fields.get(fname)
            if not field:
                continue
            value = parent[fname]
            if field.type == "many2one":
                vals[fname] = value.id if value else False
                snapshot[fname] = {"new": value.display_name if value else None}
            else:
                vals[fname] = value
                snapshot[fname] = {"new": value}

        applied = 0
        for child in self.affected_partner_ids:
            before = {
                fname: (
                    child[fname].id if parent._fields[fname].type == "many2one"
                    else child[fname]
                )
                for fname in watched if fname in child._fields
            }
            try:
                child.write(vals)
            except Exception as exc:
                _logger.warning(
                    "partner_cascade: write failed on child %s: %s",
                    child.id, exc,
                )
                continue
            # chatter on child
            diffs = []
            for fname in watched:
                new_val = vals.get(fname)
                old_val = before.get(fname)
                if old_val != new_val:
                    diffs.append("%s: %s → %s" % (fname, old_val, new_val))
            if diffs:
                try:
                    child.message_post(
                        body=_(
                            "Cascaded from parent <b>%(parent)s</b>:<br/>%(diffs)s"
                        ) % {
                            "parent": parent.display_name,
                            "diffs": "<br/>".join(diffs),
                        },
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception:
                    pass
            applied += 1

        # chatter on parent + log row
        try:
            parent.message_post(
                body=_(
                    "Cascaded master-data to <b>%(n)s</b> child contact(s). "
                    "Fields: %(fields)s"
                ) % {"n": applied, "fields": ", ".join(watched)},
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass

        self.env["cm_sa.cascade.log"].create({
            "parent_id": parent.id,
            "applied_by": self.env.user.id,
            "changes": json.dumps(snapshot),
            "count_applied": applied,
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cascade applied"),
                "message": _("Updated %s child contact(s).") % applied,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
