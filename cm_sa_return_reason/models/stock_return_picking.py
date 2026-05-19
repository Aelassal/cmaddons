import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    cm_sa_return_reason = fields.Text(
        string="Return Reason",
        help="Required typed reason for this return. Logged for QA "
             "analytics.",
    )
    cm_sa_return_category_id = fields.Many2one(
        "cm_sa.return.reason.category",
        string="Reason Category",
        domain="[('active', '=', True)]",
        help="Optional pre-defined category. Required if the config has "
             "'Require Category' on.",
    )
    cm_sa_min_reason_length = fields.Integer(
        compute="_compute_config", store=False,
    )
    cm_sa_require_category = fields.Boolean(
        compute="_compute_config", store=False,
    )

    @api.depends_context("uid")
    def _compute_config(self):
        Config = self.env["cm_sa.return.reason.config"].sudo()
        try:
            cfg = Config.get_singleton()
        except Exception:
            cfg = None
        min_len = cfg.min_reason_length if cfg else 10
        req_cat = bool(cfg and cfg.require_category)
        for rec in self:
            rec.cm_sa_min_reason_length = min_len
            rec.cm_sa_require_category = req_cat

    def _cm_sa_validate_reason(self):
        """Raise if reason missing or too short, or category required/missing."""
        self.ensure_one()
        Config = self.env["cm_sa.return.reason.config"].sudo()
        cfg = Config.get_singleton()
        if not cfg.active:
            return
        reason = (self.cm_sa_return_reason or "").strip()
        if cfg.min_reason_length:
            if len(reason) < cfg.min_reason_length:
                raise UserError(_(
                    "Return Reason is required (minimum %d characters)."
                ) % cfg.min_reason_length)
        elif not reason:
            raise UserError(_("Return Reason is required."))
        if cfg.require_category and not self.cm_sa_return_category_id:
            raise UserError(_("Please pick a Return Reason Category."))

    def _cm_sa_write_log(self, new_picking_ids):
        self.ensure_one()
        Log = self.env["cm_sa.return.reason.log"].sudo()
        Config = self.env["cm_sa.return.reason.config"].sudo()
        cfg = Config.get_singleton()

        new_pickings = self.env["stock.picking"].browse(new_picking_ids)
        return_picking = new_pickings[:1] if new_pickings else False

        line_vals = []
        for line in self.product_return_moves:
            if not line.product_id:
                continue
            line_vals.append((0, 0, {
                "product_id": line.product_id.id,
                "qty": line.quantity or 0.0,
            }))

        log = Log.create({
            "source_picking_id": self.picking_id.id if self.picking_id else False,
            "return_picking_id": return_picking.id if return_picking else False,
            "user_id": self.env.user.id,
            "category_id": self.cm_sa_return_category_id.id or False,
            "reason": self.cm_sa_return_reason or "",
            "line_ids": line_vals,
        })

        if cfg.post_chatter_note and self.picking_id:
            try:
                self.picking_id.message_post(
                    body=_(
                        "Customer return created with reason <b>%(cat)s</b>: "
                        "%(reason)s"
                    ) % {
                        "cat": self.cm_sa_return_category_id.name or _("(uncategorized)"),
                        "reason": (self.cm_sa_return_reason or "")[:500],
                    },
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            except Exception:
                pass
        return log

    def _create_returns(self):
        """Newer Odoo return-wizard API (19.0+)."""
        self._cm_sa_validate_reason()
        res = super()._create_returns()
        try:
            self._cm_sa_write_log(self._cm_sa_extract_ids(res))
        except Exception:
            _logger.exception("ReturnReason: log write failed.")
        return res

    def create_returns(self):
        """Legacy / older Odoo API."""
        self._cm_sa_validate_reason()
        res = super().create_returns() if hasattr(super(), "create_returns") else None
        try:
            self._cm_sa_write_log(self._cm_sa_extract_ids(res))
        except Exception:
            _logger.exception("ReturnReason: log write failed.")
        return res

    @staticmethod
    def _cm_sa_extract_ids(result):
        """``_create_returns`` returns either a picking id, a dict action,
        or a list. Normalise to a list of ids."""
        if not result:
            return []
        if isinstance(result, int):
            return [result]
        if isinstance(result, (list, tuple)):
            return [x for x in result if isinstance(x, int)]
        if isinstance(result, dict):
            res_id = result.get("res_id")
            if res_id:
                return [res_id]
            dom = result.get("domain")
            if dom:
                # domain is [('id', 'in', [...])] or similar
                for clause in dom:
                    if isinstance(clause, (list, tuple)) and len(clause) == 3:
                        if clause[0] == "id" and isinstance(clause[2], (list, tuple)):
                            return list(clause[2])
        return []
