import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_MARKER = "_cm_sa_attachment_size_wrapper"
_ORIGINAL = "_cm_sa_attachment_size_original"
CTX_BYPASS = "cm_sa_attachment_size_bypass"


class CmSaAttachmentSizeRule(models.Model):
    _name = "cm_sa.attachment.size.rule"
    _description = "Attachment Size Rule"
    _order = "model_id, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(
        related="model_id.model", store=True, readonly=True,
        string="Technical Model Name", index=True,
    )
    max_mb = fields.Float(
        string="Max Size (MB)",
        required=True,
        default=25.0,
        help="Maximum attachment size in megabytes. Uploads larger than "
             "this raise UserError.",
    )
    bypass_group_id = fields.Many2one(
        "res.groups",
        string="Bypass Group",
        help="Members of this group can upload over the limit. The upload "
             "still writes a bypass-log row.",
    )
    error_message = fields.Char(
        default="Attachment exceeds the %(max).1f MB limit on %(model)s "
                "(this upload: %(size).1f MB).",
        required=True,
        help="Placeholders: %(max).1f, %(model)s, %(size).1f",
    )

    log_ids = fields.One2many(
        "cm_sa.attachment.size.log", "rule_id", readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "An attachment-size rule with this name already exists.",
    )
    _model_unique = models.Constraint(
        "unique(model_id)",
        "Each model can have only one attachment-size rule.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("max_mb")
    def _check_max_mb(self):
        for rec in self:
            if rec.max_mb <= 0:
                raise ValidationError(_("Max Size (MB) must be > 0."))

    # ------------------------------------------------------------------
    # Registry hook
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return
        if "ir.attachment" not in self.env.registry:
            return
        cls = type(self.env["ir.attachment"])
        original = getattr(cls, "create", None)
        if original is None:
            return
        if getattr(original, _MARKER, False):
            original = getattr(original, _ORIGINAL, original)
        wrapper = self._build_wrapper(original)
        setattr(wrapper, _MARKER, True)
        setattr(wrapper, _ORIGINAL, original)
        wrapper.__name__ = "create"
        wrapper.__qualname__ = f"{cls.__name__}.create"
        setattr(cls, "create", wrapper)
        _logger.info(
            "AttachmentSize: installed wrapper on ir.attachment.create."
        )

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
        def guarded(self, vals_list):
            Rule = self.env["cm_sa.attachment.size.rule"].sudo()
            Log = self.env["cm_sa.attachment.size.log"].sudo()

            if self.env.context.get(CTX_BYPASS):
                return original(self, vals_list)

            vals_list_norm = vals_list if isinstance(vals_list, list) else [vals_list]
            rules_by_model = {}
            for rule in Rule.search([("active", "=", True)]):
                if rule.model_name:
                    rules_by_model[rule.model_name] = rule

            if not rules_by_model:
                return original(self, vals_list)

            for vals in vals_list_norm:
                res_model = vals.get("res_model")
                if not res_model or res_model not in rules_by_model:
                    continue
                rule = rules_by_model[res_model]

                raw = vals.get("raw")
                datas = vals.get("datas")
                file_size = vals.get("file_size") or 0
                if not file_size:
                    if raw is not None:
                        try:
                            file_size = len(raw)
                        except Exception:
                            file_size = 0
                    elif datas:
                        try:
                            import base64
                            file_size = (len(datas) * 3) // 4
                        except Exception:
                            file_size = 0
                size_mb = (file_size or 0) / (1024 * 1024)
                if size_mb <= rule.max_mb:
                    continue

                in_bypass = (
                    rule.bypass_group_id
                    and rule.bypass_group_id in self.env.user.groups_id
                )
                if not in_bypass:
                    raise UserError(rule.error_message % {
                        "max": rule.max_mb,
                        "model": rule.model_id.name or res_model,
                        "size": size_mb,
                    })
                # Bypass — log + let through
                try:
                    Log.with_context(**{CTX_BYPASS: True}).create({
                        "rule_id": rule.id,
                        "res_model": res_model,
                        "res_id": vals.get("res_id") or 0,
                        "user_id": self.env.user.id,
                        "attachment_name": vals.get("name") or "",
                        "size_mb": size_mb,
                        "limit_mb": rule.max_mb,
                    })
                except Exception:
                    _logger.exception("AttachmentSize: bypass log failed")

            return original(self, vals_list)

        return guarded

    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug("AttachmentSize: registry signal unavailable")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"active", "model_id", "max_mb", "bypass_group_id"}.intersection(vals):
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
            "res_model": "cm_sa.attachment.size.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
