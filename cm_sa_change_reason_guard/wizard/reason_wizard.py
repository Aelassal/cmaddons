import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CmSaReasonWizard(models.TransientModel):
    _name = "cm_sa.reason.wizard"
    _description = "Change with Reason Wizard"

    rule_id = fields.Many2one(
        "cm_sa.reason.rule",
        string="Rule",
        required=True,
    )
    res_model = fields.Char(string="Target Model", required=True)
    res_id = fields.Integer(string="Target Record ID")
    record_display = fields.Char(
        compute="_compute_record_display",
        readonly=True,
    )
    pending_values = fields.Text(
        help="JSON {field_name: new_value} of the proposed changes.",
        default="{}",
    )
    category_id = fields.Many2one(
        "cm_sa.reason.category",
        string="Reason Category",
    )
    note = fields.Text()

    @api.depends("res_model", "res_id")
    def _compute_record_display(self):
        for wiz in self:
            if wiz.res_model and wiz.res_id:
                try:
                    record = self.env[wiz.res_model].browse(wiz.res_id)
                    wiz.record_display = record.display_name
                except Exception:
                    wiz.record_display = "%s,%s" % (wiz.res_model, wiz.res_id)
            else:
                wiz.record_display = ""

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # When launched via the cog binding, Odoo sends active_id / active_ids
        ctx = self.env.context
        if not res.get("res_id"):
            res_id = ctx.get("active_id")
            if not res_id and ctx.get("active_ids"):
                res_id = ctx["active_ids"][0]
            if res_id:
                res["res_id"] = res_id
        if not res.get("res_model"):
            res["res_model"] = ctx.get("active_model") or res.get("res_model")
        return res

    def action_apply(self):
        self.ensure_one()
        rule = self.rule_id
        if not rule:
            raise UserError(_("No rule bound to this wizard."))
        if rule.reason_category_ids and not self.category_id:
            raise UserError(_("Pick a reason category."))
        if rule.require_note:
            if not self.note or len(self.note.strip()) < rule.min_note_chars:
                raise UserError(_(
                    "Please provide a note of at least %s characters."
                ) % rule.min_note_chars)

        try:
            vals = json.loads(self.pending_values or "{}")
        except Exception:
            raise UserError(_("Pending values must be valid JSON."))
        if not isinstance(vals, dict) or not vals:
            raise UserError(_(
                "No field changes proposed. Add entries to Pending Values "
                "in the form {\"field\": \"new value\"}."
            ))
        allowed = set(rule.field_ids.mapped("name"))
        for key in vals:
            if key not in allowed:
                raise UserError(_(
                    "Field '%s' is not among the fields guarded by this rule."
                ) % key)

        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_("Target record no longer exists."))

        old = {}
        for fname in vals:
            value = record[fname]
            old[fname] = value.id if hasattr(value, "id") else value

        record.write(vals)

        # Chatter audit
        diffs = []
        for fname, new_val in vals.items():
            diffs.append("%s: %r → %r" % (fname, old.get(fname), new_val))
        cat = self.category_id.display_name if self.category_id else _("(none)")
        if hasattr(record, "message_post"):
            try:
                record.message_post(
                    body=_(
                        "Guarded change (rule: <b>%(rule)s</b>, category: "
                        "<b>%(cat)s</b>):<br/>%(diffs)s<br/><i>%(note)s</i>"
                    ) % {
                        "rule": rule.name,
                        "cat": cat,
                        "diffs": "<br/>".join(diffs),
                        "note": self.note or "",
                    },
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:
                pass

        self.env["cm_sa.reason.log"].create({
            "rule_id": rule.id,
            "res_model": self.res_model,
            "res_id": self.res_id,
            "user_id": self.env.user.id,
            "changed_field_names": ", ".join(vals.keys()),
            "category_id": self.category_id.id if self.category_id else False,
            "note": self.note or "",
            "old_values_json": json.dumps(old, default=str),
            "new_values_json": json.dumps(vals, default=str),
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Change applied"),
                "message": _("%s field(s) updated with a logged reason.") % len(vals),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
