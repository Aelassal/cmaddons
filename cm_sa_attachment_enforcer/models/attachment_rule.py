import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_ENF_MARKER = "_cm_sa_attachment_enforcer_wrapper"
_ENF_ORIGINAL = "_cm_sa_attachment_enforcer_original"

CTX_REASON = "cm_sa_attachment_bypass_reason"
CTX_BYPASS = "cm_sa_attachment_enforcer_bypass"


class CmSaAttachmentRule(models.Model):
    _name = "cm_sa.attachment.rule"
    _description = "Invoice Attachment Rule"
    _order = "name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    move_type = fields.Selection(
        [
            ("any", "Any Move Type"),
            ("in_invoice", "Vendor Bills only"),
            ("out_invoice", "Customer Invoices only"),
            ("in_refund", "Vendor Credit Notes only"),
            ("out_refund", "Customer Credit Notes only"),
        ],
        default="any",
        required=True,
    )
    journal_ids = fields.Many2many(
        "account.journal",
        "cm_sa_attach_rule_journal_rel",
        "rule_id", "journal_id",
        string="Specific Journals",
        help="Leave empty to apply the rule regardless of journal.",
    )
    min_attachments = fields.Integer(
        default=1,
        required=True,
        help="Minimum number of attachments required on the move before post. "
             "Use 1 for the common 'at least one PDF' case.",
    )
    allowed_mimetypes = fields.Char(
        string="Allowed Mime Types",
        help="Optional CSV, e.g. 'application/pdf, image/png'. Leave empty "
             "to accept any mime type. Match is exact, case-insensitive.",
    )
    bypass_group_id = fields.Many2one(
        "res.groups",
        string="Bypass Group",
        help="Members of this group can post without the required "
             "attachment(s), after filling a bypass-reason wizard.",
    )
    require_bypass_reason = fields.Boolean(
        default=True,
        help="When on, bypass opens a wizard asking for a typed reason.",
    )
    min_bypass_reason_length = fields.Integer(
        default=10,
        help="Minimum characters required in the bypass reason.",
    )
    error_message = fields.Char(
        default="This %(move)s cannot be posted without at least %(n)s "
                "attachment(s). Attach the supporting PDF or request a "
                "bypass.",
        required=True,
        help="Placeholders: %(move)s, %(n)s.",
    )

    log_ids = fields.One2many(
        "cm_sa.attachment.bypass.log", "rule_id", readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "An attachment rule with this name already exists.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("min_attachments", "min_bypass_reason_length")
    def _check_numbers(self):
        for rec in self:
            if rec.min_attachments < 0:
                raise ValidationError(_("Min Attachments must be >= 0."))
            if rec.min_bypass_reason_length < 0:
                raise ValidationError(_(
                    "Min Bypass Reason Length must be >= 0."
                ))

    # ------------------------------------------------------------------
    # Registry hook
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return
        try:
            self.sudo().search([("active", "=", True)])
        except Exception:
            _logger.exception(
                "AttachmentEnforcer: could not load rules; no wrappers installed."
            )
            return
        if "account.move" not in self.env.registry:
            return
        cls = type(self.env["account.move"])
        original = getattr(cls, "action_post", None)
        if original is None:
            return
        if getattr(original, _ENF_MARKER, False):
            original = getattr(original, _ENF_ORIGINAL, original)

        wrapper = self._build_wrapper(original)
        setattr(wrapper, _ENF_MARKER, True)
        setattr(wrapper, _ENF_ORIGINAL, original)
        wrapper.__name__ = "action_post"
        wrapper.__qualname__ = f"{cls.__name__}.action_post"
        setattr(cls, "action_post", wrapper)
        _logger.info("AttachmentEnforcer: installed wrapper on account.move.action_post.")

    def _table_exists(self):
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (self._table,),
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    @staticmethod
    def _build_wrapper(original):
        def guarded(self, *args, **kwargs):
            Rule = self.env["cm_sa.attachment.rule"].sudo()
            Log = self.env["cm_sa.attachment.bypass.log"].sudo()

            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            rules = Rule.search([("active", "=", True)])
            if not rules:
                return original(self, *args, **kwargs)

            reason_from_ctx = (self.env.context.get(CTX_REASON) or "").strip()

            for move in self:
                # Which rules apply to this move?
                applicable = Rule
                for rule in rules:
                    if rule.move_type != "any" and rule.move_type != move.move_type:
                        continue
                    if rule.journal_ids and move.journal_id not in rule.journal_ids:
                        continue
                    applicable |= rule

                if not applicable:
                    continue

                # Check attachments on this move
                attachments = self.env["ir.attachment"].sudo().search([
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                ])

                for rule in applicable:
                    ok = len(attachments) >= rule.min_attachments
                    if ok and rule.allowed_mimetypes:
                        allowed = {
                            mt.strip().lower()
                            for mt in rule.allowed_mimetypes.split(",")
                            if mt.strip()
                        }

                        def _attachment_type_ok(attachment):
                            mimetype = (attachment.mimetype or "").lower()
                            filename = (attachment.name or "").lower()

                            if mimetype in allowed:
                                return True

                            if "application/pdf" in allowed and filename.endswith(".pdf"):
                                return True

                            return False

                        valid_count = sum(1 for attachment in attachments if _attachment_type_ok(attachment))
                        ok = valid_count >= rule.min_attachments

                    if ok:
                        continue  # rule satisfied

                    # Rule not satisfied — bypass?
                    in_bypass = (
                        rule.bypass_group_id
                        and rule.bypass_group_id in self.env.user.groups_id
                    )
                    if not in_bypass:
                        raise UserError(
                            rule.error_message % {
                                "move": move.display_name or move.name or str(move.id),
                                "n": rule.min_attachments,
                            }
                        )

                    # Bypass path — require reason if configured and not in context
                    if rule.require_bypass_reason and not reason_from_ctx:
                        return {
                            "type": "ir.actions.act_window",
                            "name": _("Attachment Bypass — Reason Required"),
                            "res_model": "cm_sa.attachment.bypass.wizard",
                            "view_mode": "form",
                            "target": "new",
                            "context": {
                                "default_rule_id": rule.id,
                                "default_move_id_str": ",".join(str(m.id) for m in self),
                                "default_min_length": rule.min_bypass_reason_length,
                            },
                        }
                    if (rule.require_bypass_reason
                            and rule.min_bypass_reason_length
                            and len(reason_from_ctx) < rule.min_bypass_reason_length):
                        raise UserError(_(
                            "Bypass reason must be at least %d characters."
                        ) % rule.min_bypass_reason_length)

                    # Log the bypass and let the post through
                    try:
                        Log.with_context(**{CTX_BYPASS: True}).create({
                            "rule_id": rule.id,
                            "move_id": move.id,
                            "user_id": self.env.user.id,
                            "reason": reason_from_ctx,
                            "attachment_count_at_bypass": len(attachments),
                        })
                    except Exception:
                        _logger.exception(
                            "AttachmentEnforcer: bypass log write failed for move %s",
                            move.id,
                        )
                    try:
                        move.message_post(
                            body=_(
                                "Attachment Enforcer bypass by <b>%(user)s</b>. "
                                "Rule: <b>%(rule)s</b>. Reason: %(reason)s"
                            ) % {
                                "user": self.env.user.display_name,
                                "rule": rule.name,
                                "reason": reason_from_ctx or _("(none)"),
                            },
                            message_type="comment",
                            subtype_xmlid="mail.mt_note",
                        )
                    except Exception:
                        pass

            return original(self, *args, **kwargs)

        return guarded

    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug("AttachmentEnforcer: registry.signal_changes() unavailable.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"active"}.intersection(vals):
            self._signal_registry()
        return res

    def unlink(self):
        res = super().unlink()
        self._signal_registry()
        return res

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bypass Log"),
            "res_model": "cm_sa.attachment.bypass.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
