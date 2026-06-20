import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaNegativeStockConfig(models.Model):
    """Singleton holding scan settings. One row per database."""

    _name = "cm_sa.negative.stock.config"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Negative Inventory Scanner Configuration"
    _order = "id"

    name = fields.Char(default="Negative Stock Scanner", required=True)
    active = fields.Boolean(default=True)
    min_days_negative = fields.Integer(
        default=0,
        help="Only include products that have been negative for at least "
             "this many days (based on the quant's write_date). Use 0 to "
             "include all current-negative quants.",
    )
    notify_user_ids = fields.Many2many(
        "res.users",
        "cm_sa_negstock_notify_rel",
        "config_id",
        "user_id",
        string="Notify Users",
        help="Recipients of the weekly digest email.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Optional extra domain on stock.quant. Example: "
             "[('location_id.usage', '=', 'internal')]",
    )
    include_internal_only = fields.Boolean(
        default=True,
        help="Restrict to internal locations (exclude transit, customer, "
             "supplier, inventory loss, etc.). On by default — transit "
             "locations legitimately hold negative values.",
    )
    snapshot_ids = fields.One2many(
        "cm_sa.negative.stock.snapshot", "config_id",
    )
    snapshot_count = fields.Integer(compute="_compute_snapshot_count")

    @api.depends("snapshot_ids")
    def _compute_snapshot_count(self):
        for rec in self:
            rec.snapshot_count = len(rec.snapshot_ids)

    @api.constrains("min_days_negative")
    def _check_min_days(self):
        for rec in self:
            if rec.min_days_negative < 0:
                raise ValidationError(_("Minimum days negative must be >= 0."))

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                v = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(
                    _("Extra Domain is not valid: %s") % exc
                )
            if not isinstance(v, list):
                raise ValidationError(_("Extra Domain must evaluate to a list."))

    @api.model
    def get_singleton(self):
        # active_test=False so an archived config is reused rather than
        # spawning a duplicate alongside it.
        rec = self.with_context(active_test=False).search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    def _build_quant_domain(self):
        self.ensure_one()
        # Scope to the current company so the scan respects multi-company:
        # only the company the user is working in is considered.
        domain = [
            ("quantity", "<", 0),
            ("company_id", "=", self.env.company.id),
        ]
        if self.include_internal_only:
            domain += [("location_id.usage", "=", "internal")]
        try:
            domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        except Exception:
            _logger.exception("NegativeStockScanner: invalid extra_domain")
        _logger.info(
            "NegativeStockScanner[%s]: quant domain = %s "
            "(company=%s id=%s, include_internal_only=%s)",
            self.name, domain, self.env.company.display_name,
            self.env.company.id, self.include_internal_only,
        )
        return domain

    def _run_scan(self, triggered_by="cron"):
        self.ensure_one()
        Quant = self.env["stock.quant"].sudo()
        Snapshot = self.env["cm_sa.negative.stock.snapshot"].sudo()
        Line = self.env["cm_sa.negative.stock.line"].sudo()

        company = self.env.company
        _logger.info(
            "NegativeStockScanner[%s]: starting scan (trigger=%s) as user=%s, "
            "env.company=%s (id=%s), allowed_companies=%s",
            self.name, triggered_by, self.env.user.login,
            company.display_name, company.id, self.env.companies.ids,
        )
        quants = Quant.search(self._build_quant_domain())
        today = fields.Date.context_today(self)
        _logger.info(
            "NegativeStockScanner[%s]: %s negative quant(s) matched: %s",
            self.name, len(quants),
            [
                (q.product_id.display_name, q.location_id.display_name,
                 q.quantity, q.company_id.display_name)
                for q in quants
            ],
        )

        # The negativity decision is driven by the product's net availability
        # (qty_available) evaluated in the CURRENT company, not by individual
        # quant rows. A product that is -8 in one bin but positive overall is
        # not negative stock; multi-company on-hand stays isolated per company.
        # qty_available < 0 implies at least one negative internal quant, so
        # scanning the company's negative quants never misses a net-negative
        # product while letting us keep the per-location breakdown and aging.
        # Pin allowed_company_ids too: with_company alone keeps other open
        # companies in context, and qty_available's location domain is built
        # from env.companies — so qty_available must be restricted to this one
        # company to stay isolated.
        products = quants.product_id.with_company(company).with_context(
            allowed_company_ids=[company.id],
        )
        negative_product_ids = set()
        for product in products:
            qty = product.qty_available
            is_negative = float_compare(
                qty, 0.0, precision_rounding=product.uom_id.rounding,
            ) < 0
            _logger.info(
                "NegativeStockScanner[%s]: product %s qty_available=%s "
                "(company=%s) -> %s",
                self.name, product.display_name, qty, company.display_name,
                "NEGATIVE" if is_negative else "ok",
            )
            if is_negative:
                negative_product_ids.add(product.id)
        _logger.info(
            "NegativeStockScanner[%s]: %s product(s) net-negative: %s",
            self.name, len(negative_product_ids), sorted(negative_product_ids),
        )

        snapshot = Snapshot.create({
            "config_id": self.id,
            "triggered_by": triggered_by,
            "scan_date": today,
        })

        line_vals = []
        for quant in quants:
            if quant.product_id.id not in negative_product_ids:
                continue
            wdate = fields.Date.to_date(quant.write_date) if quant.write_date else today
            aging_days = (today - wdate).days if wdate else 0
            if aging_days < self.min_days_negative:
                continue
            line_vals.append({
                "snapshot_id": snapshot.id,
                "product_id": quant.product_id.id,
                "location_id": quant.location_id.id,
                "quantity": quant.quantity,
                "aging_days": aging_days,
                "write_date_first": wdate,
            })
        if line_vals:
            Line.create(line_vals)
        _logger.info(
            "NegativeStockScanner[%s]: snapshot %s created with %s line(s) "
            "(min_days_negative=%s)",
            self.name, snapshot.id, len(line_vals), self.min_days_negative,
        )

        # Recompute totals
        snapshot._compute_totals()

        # Send digest to notify users
        if self.notify_user_ids and line_vals:
            try:
                self._send_digest(snapshot)
            except Exception:
                _logger.exception(
                    "NegativeStockScanner: digest send failed for snapshot %s",
                    snapshot.id,
                )
        return snapshot

    def _send_digest(self, snapshot):
        self.ensure_one()
        partners = [u.partner_id.id for u in self.notify_user_ids if u.partner_id]
        if not partners:
            return
        Mail = self.env["mail.mail"].sudo()
        body_lines = [
            _("<p>Negative stock scan on %s — %d line(s), %d location(s).</p>")
            % (snapshot.scan_date, snapshot.line_count, snapshot.location_count),
            "<table border='1' cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse;font-family:sans-serif;font-size:12px;'>",
            "<thead><tr style='background:#f2f5f9;'>"
            "<th>Location</th><th>Product</th><th>Qty</th><th>Aging (days)</th>"
            "</tr></thead><tbody>",
        ]
        for line in snapshot.line_ids.sorted(key=lambda l: -l.aging_days)[:100]:
            body_lines.append(
                f"<tr><td>{line.location_id.display_name}</td>"
                f"<td>{line.product_id.display_name}</td>"
                f"<td style='text-align:right;color:#e53e3e;'>"
                f"{line.quantity}</td>"
                f"<td style='text-align:right;'>{line.aging_days}</td></tr>"
            )
        body_lines.append("</tbody></table>")
        if snapshot.line_count > 100:
            body_lines.append(
                _("<p>… and %d more. Open the snapshot for the full list.</p>")
                % (snapshot.line_count - 100)
            )
        subject = _("[Negative Stock] %d line(s) as of %s") % (
            snapshot.line_count, snapshot.scan_date,
        )
        try:
            Mail.create({
                "subject": subject,
                "body_html": "".join(body_lines),
                "recipient_ids": [(6, 0, partners)],
                "author_id": self.env.user.partner_id.id,
            }).send()
        except Exception:
            _logger.exception("NegativeStockScanner: mail send failed")

    @api.model
    def _cron_scan(self):
        # Ensure the singleton exists so a fresh DB (where the config form /
        # wizard was never opened) still scans instead of silently doing
        # nothing.
        self.get_singleton()
        configs = self.search([("active", "=", True)])
        _logger.info(
            "NegativeStockScanner cron: %s active config(s) found, "
            "running as user=%s, env.company=%s (id=%s)",
            len(configs), self.env.user.login,
            self.env.company.display_name, self.env.company.id,
        )
        for cfg in configs:
            try:
                cfg._run_scan(triggered_by="cron")
            except Exception:
                _logger.exception(
                    "NegativeStockScanner cron failed for config %s", cfg.id,
                )

    def action_scan_now(self):
        """Run immediately and open the resulting snapshot."""
        self.ensure_one()
        snapshot = self._run_scan(triggered_by="manual")
        return {
            "type": "ir.actions.act_window",
            "name": _("Negative Stock Snapshot"),
            "res_model": "cm_sa.negative.stock.snapshot",
            "res_id": snapshot.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_snapshots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Snapshots"),
            "res_model": "cm_sa.negative.stock.snapshot",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
        }
