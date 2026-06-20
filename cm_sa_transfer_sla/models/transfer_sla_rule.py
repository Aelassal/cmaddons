import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaTransferSlaRule(models.Model):
    _name = "cm_sa.transfer.sla.rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Warehouse Transfer SLA Rule"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        "cm_sa_transfer_sla_picktype_rel",
        "rule_id", "picking_type_id",
        string="Operation Types",
        help="Limit to these operation types (Internal / Incoming / "
             "Outgoing / Manufacturing). Leave empty to cover all.",
    )
    source_location_ids = fields.Many2many(
        "stock.location",
        "cm_sa_transfer_sla_src_rel",
        "rule_id", "location_id",
        string="Source Locations",
        compute="_compute_locations_from_picking_types",
        store=True, readonly=False,
        help="Limit to pickings moving FROM these locations. Auto-filled "
             "from the selected operation types' default source location "
             "(like a stock picking); editable. Leave empty to ignore "
             "source.",
    )
    dest_location_ids = fields.Many2many(
        "stock.location",
        "cm_sa_transfer_sla_dst_rel",
        "rule_id", "location_id",
        string="Destination Locations",
        compute="_compute_locations_from_picking_types",
        store=True, readonly=False,
        help="Limit to pickings moving TO these locations. Auto-filled "
             "from the selected operation types' default destination "
             "location (like a stock picking); editable. Leave empty to "
             "ignore destination.",
    )
    max_days_in_transit = fields.Integer(
        default=5,
        required=True,
        help="Alert when (now - scheduled_date) exceeds this threshold and "
             "the picking hasn't been completed.",
    )
    escalation_buckets_csv = fields.Char(
        string="Escalation Buckets (extra days)",
        default="5,10",
        help="Comma-separated extra-days thresholds on top of "
             "max_days_in_transit. A picking 'max + 5' days overdue "
             "re-alerts at the next bucket. Empty = one-shot alert only.",
    )
    notify_user_ids = fields.Many2many(
        "res.users",
        "cm_sa_transfer_sla_notify_rel",
        "rule_id", "user_id",
        string="Notify Users",
        help="Recipients of the overdue email. Plus the picking's responsible "
             "user when set.",
    )
    notify_responsible = fields.Boolean(
        default=True,
        help="Email the picking's responsible (stock.picking.user_id) in "
             "addition to the notify users.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Optional extra Odoo domain on stock.picking, e.g. "
             "[('company_id', '=', 1)]",
    )

    last_run = fields.Datetime(readonly=True)
    log_ids = fields.One2many(
        "cm_sa.transfer.sla.log", "rule_id", readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A transfer-SLA rule with this name already exists.",
    )

    @api.depends("picking_type_ids")
    def _compute_locations_from_picking_types(self):
        """Default the source/dest filters from the chosen operation types.

        Mirrors stock.picking._compute_location_id: picking the operation
        type(s) pulls in their default source/destination locations. The
        fields stay editable (store=True, readonly=False), so users can
        refine or clear the suggestion afterwards. Selecting/clearing the
        operation types re-applies the defaults.
        """
        for rule in self:
            # Many2one accessed on a multi-record set yields the union of
            # the related records, so this collects every type's default.
            rule.source_location_ids = rule.picking_type_ids.default_location_src_id
            rule.dest_location_ids = rule.picking_type_ids.default_location_dest_id

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("max_days_in_transit")
    def _check_max_days(self):
        for rec in self:
            if rec.max_days_in_transit <= 0:
                raise ValidationError(_("Max Days in Transit must be > 0."))

    @api.constrains("escalation_buckets_csv")
    def _check_buckets(self):
        for rec in self:
            if not rec.escalation_buckets_csv:
                continue
            try:
                ths = rec._parse_buckets()
            except Exception as exc:
                raise ValidationError(_(
                    "Escalation Buckets must be a comma-separated list of "
                    "positive integers: %s"
                ) % exc)
            if any(t <= 0 for t in ths):
                raise ValidationError(_("Buckets must be positive."))

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                value = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(_("Extra Domain is not valid: %s") % exc)
            if not isinstance(value, list):
                raise ValidationError(_("Extra Domain must evaluate to a list."))

    def _parse_buckets(self):
        self.ensure_one()
        import re
        if not self.escalation_buckets_csv:
            return []
        parts = [p.strip() for p in re.split(r"[,\s]+", self.escalation_buckets_csv) if p.strip()]
        return sorted({int(p) for p in parts})

    def _candidate_domain(self):
        self.ensure_one()
        domain = [
            ("state", "in", ("assigned", "waiting", "confirmed")),
            ("scheduled_date", "!=", False),
        ]
        if self.picking_type_ids:
            domain += [("picking_type_id", "in", self.picking_type_ids.ids)]
        if self.source_location_ids:
            domain += [("location_id", "in", self.source_location_ids.ids)]
        if self.dest_location_ids:
            domain += [("location_dest_id", "in", self.dest_location_ids.ids)]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _applicable_bucket(self, days_overdue):
        """Return the highest bucket the picking has crossed.

        Bucket 0 = crossed the base threshold (max_days_in_transit).
        Bucket N (1-indexed) = crossed max + sum(first N extra buckets).

        A single "effective days overdue" maps to one bucket key so the
        dedupe stays clean.
        """
        self.ensure_one()
        if days_overdue < self.max_days_in_transit:
            return None
        try:
            extras = self._parse_buckets()
        except Exception:
            extras = []
        bucket_key = 0
        accumulated = self.max_days_in_transit
        for i, extra in enumerate(extras, start=1):
            accumulated += extra
            if days_overdue >= accumulated:
                bucket_key = i
        return bucket_key

    def _run_one(self):
        self.ensure_one()
        Picking = self.env["stock.picking"].sudo()
        Log = self.env["cm_sa.transfer.sla.log"].sudo()
        now = fields.Datetime.now()

        try:
            pickings = Picking.search(self._candidate_domain())
        except Exception as exc:
            _logger.exception(
                "TransferSLA rule %s: search failed: %s", self.name, exc,
            )
            return 0

        sent = 0
        for picking in pickings:
            try:
                if not picking.scheduled_date:
                    continue
                days_overdue = (now - picking.scheduled_date).days
                bucket = self._applicable_bucket(days_overdue)
                if bucket is None:
                    continue
                already = Log.search_count([
                    ("rule_id", "=", self.id),
                    ("picking_id", "=", picking.id),
                    ("bucket_key", "=", bucket),
                ])
                if already:
                    continue
                # Log + notify
                try:
                    Log.create({
                        "rule_id": self.id,
                        "picking_id": picking.id,
                        "days_overdue": days_overdue,
                        "bucket_key": bucket,
                        "scheduled_date": picking.scheduled_date,
                    })
                except Exception:
                    _logger.exception(
                        "TransferSLA: log write failed for picking %s", picking.id,
                    )
                    continue
                try:
                    self._notify(picking, days_overdue, bucket)
                    sent += 1
                except Exception:
                    _logger.exception(
                        "TransferSLA: notify failed for picking %s", picking.id,
                    )
            except Exception:
                _logger.exception(
                    "TransferSLA rule %s: picking %s failed.",
                    self.name, picking.id,
                )
                continue

        self.write({"last_run": fields.Datetime.now()})
        return sent

    def _resolve_recipients(self, picking):
        self.ensure_one()
        partners = self.env["res.partner"]
        for u in self.notify_user_ids:
            if u.partner_id:
                partners |= u.partner_id
        if self.notify_responsible and picking.user_id and picking.user_id.partner_id:
            partners |= picking.user_id.partner_id
        return partners

    def _notify(self, picking, days_overdue, bucket):
        self.ensure_one()
        partners = self._resolve_recipients(picking)
        if not partners:
            return
        body = _(
            "<p>Picking <b>%(ref)s</b> (%(type)s) has been in flight "
            "for <b>%(days)s day(s)</b> past its scheduled date.</p>"
            "<p><b>Source:</b> %(src)s<br/>"
            "<b>Destination:</b> %(dst)s<br/>"
            "<b>Scheduled date:</b> %(scheduled)s<br/>"
            "<b>State:</b> %(state)s</p>"
            "<p>Escalation bucket: %(bucket)s. Rule: %(rule)s.</p>"
        ) % {
            "ref": picking.name or str(picking.id),
            "type": picking.picking_type_id.name if picking.picking_type_id else "",
            "days": days_overdue,
            "src": picking.location_id.display_name if picking.location_id else "",
            "dst": picking.location_dest_id.display_name if picking.location_dest_id else "",
            "scheduled": picking.scheduled_date or "",
            "state": picking.state or "",
            "bucket": bucket,
            "rule": self.name,
        }
        try:
            self.env["mail.mail"].sudo().create({
                "subject": _("[Transfer SLA] %(ref)s — %(days)s days overdue") % {
                    "ref": picking.name or str(picking.id),
                    "days": days_overdue,
                },
                "body_html": body,
                "recipient_ids": [(6, 0, partners.ids)],
                "author_id": self.env.user.partner_id.id,
                "model": "stock.picking",
                "res_id": picking.id,
            }).send()
        except Exception:
            _logger.exception("TransferSLA: mail send failed")
        try:
            picking.message_post(
                body=_(
                    "Transfer SLA [%(rule)s]: <b>%(days)s day(s) overdue</b> "
                    "(bucket %(bucket)s)."
                ) % {
                    "rule": self.name,
                    "days": days_overdue,
                    "bucket": bucket,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass

    @api.model
    def _cron_scan(self):
        for rule in self.search([]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("TransferSLA rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            sent = rule._run_one()
            if hasattr(rule, "message_post"):
                rule.message_post(
                    body=_("Transfer SLA manual run: %s alert(s) emailed.") % sent
                )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Transfer SLA Scan"),
                "message": _("Done. See the log for details."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SLA Alert Log"),
            "res_model": "cm_sa.transfer.sla.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
