import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        """After a write on a company partner, post a soft chatter note
        when a watched field changed so the user notices they may want to
        cascade. We do NOT auto-cascade — that's the wizard's job."""
        # Snapshot old values before the write
        watched = []
        try:
            Setting = self.env["cm_sa.cascade.setting"].sudo()
            watched = Setting._watched_field_names()
        except Exception:
            watched = []
        old_by_id = {}
        if watched:
            changed_watched = [f for f in watched if f in vals]
            if changed_watched:
                for rec in self:
                    if rec.is_company and rec.child_ids:
                        old_by_id[rec.id] = {
                            f: rec[f].id if hasattr(rec[f], "id") else rec[f]
                            for f in changed_watched
                        }

        res = super().write(vals)

        # After write: drop a chatter hint on each company partner we touched.
        if old_by_id:
            for rec in self:
                if rec.id not in old_by_id:
                    continue
                changed_fields = list(old_by_id[rec.id].keys())
                try:
                    rec.message_post(
                        body=_(
                            "Watched master-data field(s) changed: <b>%(fields)s</b>. "
                            "Use the <b>Cascade to contacts</b> button to propagate "
                            "the change to %(n)s child contact(s)."
                        ) % {
                            "fields": ", ".join(changed_fields),
                            "n": len(rec.child_ids),
                        },
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception as exc:
                    _logger.debug(
                        "partner_cascade: chatter hint failed on %s: %s",
                        rec.id, exc,
                    )
        return res

    def action_open_cascade_wizard(self):
        """Partner-form button: open the cascade wizard for this partner."""
        self.ensure_one()
        if not self.is_company:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Not a company"),
                    "message": _(
                        "Cascade only applies from a company partner to its "
                        "children. This partner is marked as an individual."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }
        if not self.child_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No contacts to cascade to"),
                    "message": _("This company has no child contacts."),
                    "type": "info",
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Cascade to Contacts"),
            "res_model": "cm_sa.cascade.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_id": self.id},
        }
