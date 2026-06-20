import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CmSaStaleOpportunityRule(models.Model):
    _name = "cm_sa.stale.opportunity.rule"
    _description = "Stale Opportunity Rule"
    _order = "name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    stale_days = fields.Integer(
        default=30,
        required=True,
        help="An opportunity is stale if its stale reference date is more "
             "than this many days old.",
    )
    warning_days = fields.Integer(
        default=7,
        required=True,
        help="Days before the close deadline to email the owner a warning. "
             "Set to 0 to skip warnings (close silently).",
    )
    stale_reference = fields.Selection(
        [
            ("write_date", "Last Edit (write_date)"),
            ("date_last_stage_update", "Last Stage Change"),
        ],
        default="write_date",
        required=True,
        help="Which timestamp to use for the staleness measurement.",
    )

    stage_ids = fields.Many2many(
        "crm.stage",
        "cm_sa_stale_opp_stage_rel",
        "rule_id", "stage_id",
        string="Apply to Stages",
        help="Only opportunities in these stages are affected. Leave empty "
             "to apply to all non-won, non-lost stages.",
    )
    team_ids = fields.Many2many(
        "crm.team",
        "cm_sa_stale_opp_team_rel",
        "rule_id", "team_id",
        string="Apply to Teams",
        help="Optional. Leave empty to apply across all teams.",
    )
    extra_domain = fields.Char(
        default="[]",
        help="Optional additional Odoo domain on crm.lead.\n"
             "Example: [('expected_revenue', '<', 10000)]",
    )

    lost_reason_id = fields.Many2one(
        "crm.lost.reason",
        string="Lost Reason",
        required=True,
        ondelete="restrict",
        help="Applied to every opportunity the rule auto-closes.",
    )
    notify_owner_on_warning = fields.Boolean(
        default=True,
        help="When on, the opportunity's salesperson receives a warning "
             "email before auto-close.",
    )
    notify_owner_on_close = fields.Boolean(
        default=True,
        help="When on, the opportunity's salesperson receives a notification "
             "email when the opportunity is auto-closed.",
    )

    last_run = fields.Datetime(readonly=True)
    log_ids = fields.One2many("cm_sa.stale.opportunity.log", "rule_id", readonly=True)
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A stale-opportunity rule with this name already exists.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("stale_days", "warning_days")
    def _check_days(self):
        for rec in self:
            if rec.stale_days <= 0:
                raise ValidationError(_("Stale Days must be > 0."))
            if rec.warning_days < 0:
                raise ValidationError(_("Warning Days must be >= 0."))
            if rec.warning_days >= rec.stale_days:
                raise ValidationError(_(
                    "Warning Days must be less than Stale Days — otherwise "
                    "warnings fire after the opportunity is already closed."
                ))

    @api.constrains("extra_domain")
    def _check_extra_domain(self):
        for rec in self:
            try:
                value = safe_eval(rec.extra_domain or "[]", {"__builtins__": {}})
            except Exception as exc:
                raise ValidationError(_("Extra Domain is not valid: %s") % exc)
            if not isinstance(value, list):
                raise ValidationError(_("Extra Domain must evaluate to a list."))

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    def _candidate_domain(self):
        """Domain on crm.lead that scopes the population this rule watches.

        Excludes won opportunities, excludes already-lost ones, keeps only
        records of type=opportunity.
        """
        self.ensure_one()
        domain = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("probability", "<", 100),  # not won
            ("probability", ">", 0),    # not already lost
        ]
        if self.stage_ids:
            domain += [("stage_id", "in", self.stage_ids.ids)]
        if self.team_ids:
            domain += [("team_id", "in", self.team_ids.ids)]
        domain += safe_eval(self.extra_domain or "[]", {"__builtins__": {}})
        return domain

    def _get_reference_date(self, lead):
        """Return the datetime field value chosen as the staleness reference."""
        self.ensure_one()
        return lead[self.stale_reference]

    def _run_one(self):
        """Scan one rule. For each candidate:

        * If (now - reference) > stale_days → close (mark lost + log).
        * Else if (now - reference) > (stale_days - warning_days) and the
          owner hasn't been warned for this (rule, lead) since the last
          touch → email a warning and log it.
        """
        self.ensure_one()
        Lead = self.env["crm.lead"].sudo()
        Log = self.env["cm_sa.stale.opportunity.log"].sudo()
        now = fields.Datetime.now()
        close_cutoff = now - timedelta(days=self.stale_days)
        warn_cutoff = now - timedelta(
            days=max(self.stale_days - self.warning_days, 0)
        )

        try:
            candidates = Lead.search(self._candidate_domain())
        except Exception as exc:
            _logger.exception(
                "StaleOpportunity rule %s: search failed: %s", self.name, exc,
            )
            return 0

        closed = 0
        warned = 0
        for lead in candidates:
            try:
                ref_dt = self._get_reference_date(lead)
                if not ref_dt:
                    continue

                if ref_dt <= close_cutoff:
                    self._close_lead(lead, Log)
                    closed += 1
                elif self.warning_days and ref_dt <= warn_cutoff:
                    # Only warn if we haven't warned for this (rule, lead, ref_dt)
                    # — re-touching the lead resets the reference date and may
                    # re-raise a warning later, which is correct.
                    already = Log.search_count([
                        ("rule_id", "=", self.id),
                        ("lead_id", "=", lead.id),
                        ("action", "=", "warned"),
                        ("reference_date", "=", ref_dt),
                    ])
                    if not already:
                        self._warn_lead(lead, ref_dt, Log)
                        warned += 1
            except Exception:
                _logger.exception(
                    "StaleOpportunity rule %s: lead %s failed.",
                    self.name, lead.id,
                )
                continue

        self.write({"last_run": fields.Datetime.now()})
        return (closed, warned)

    def _close_lead(self, lead, Log):
        self.ensure_one()
        try:
            lead.action_set_lost({"lost_reason_id": self.lost_reason_id.id})
        except TypeError:
            # Older/newer API: set fields directly
            lead.write({
                "active": False,
                "probability": 0,
                "lost_reason_id": self.lost_reason_id.id,
            })
        try:
            lead.message_post(
                body=_(
                    "Auto-closed by Stale Opportunity rule <b>%(rule)s</b> "
                    "(inactive for %(days)s day(s)). Lost reason: "
                    "<b>%(reason)s</b>."
                ) % {
                    "rule": self.name,
                    "days": self.stale_days,
                    "reason": self.lost_reason_id.name,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass

        Log.create({
            "rule_id": self.id,
            "lead_id": lead.id,
            "partner_id": lead.partner_id.id if lead.partner_id else False,
            "user_id": lead.user_id.id if lead.user_id else False,
            "action": "closed",
            "reference_date": self._get_reference_date(lead),
        })

        if self.notify_owner_on_close and lead.user_id and lead.user_id.partner_id:
            self._send_email(
                lead, lead.user_id.partner_id,
                subject=_("[Auto-Closed] %s") % lead.name,
                body=_(
                    "<p>Opportunity <b>%(name)s</b> (customer %(partner)s) "
                    "has been auto-closed as lost by rule <b>%(rule)s</b>.</p>"
                    "<p>Reason: <b>%(reason)s</b>.</p>"
                    "<p>Last activity: %(ref)s.</p>"
                ) % {
                    "name": lead.name or "",
                    "partner": (lead.partner_id.name if lead.partner_id else _("(no customer)")),
                    "rule": self.name,
                    "reason": self.lost_reason_id.name,
                    "ref": self._get_reference_date(lead) or "",
                },
            )

    def _warn_lead(self, lead, ref_dt, Log):
        self.ensure_one()
        Log.create({
            "rule_id": self.id,
            "lead_id": lead.id,
            "partner_id": lead.partner_id.id if lead.partner_id else False,
            "user_id": lead.user_id.id if lead.user_id else False,
            "action": "warned",
            "reference_date": ref_dt,
        })
        if self.notify_owner_on_warning and lead.user_id and lead.user_id.partner_id:
            self._send_email(
                lead, lead.user_id.partner_id,
                subject=_("[Stale Soon] %s") % lead.name,
                body=_(
                    "<p>Opportunity <b>%(name)s</b> (customer %(partner)s) "
                    "will be auto-closed in about <b>%(days)s day(s)</b> "
                    "unless you take action.</p>"
                    "<p>Triggering rule: <b>%(rule)s</b>. "
                    "Lost reason on close: <b>%(reason)s</b>.</p>"
                    "<p>Any edit, stage move, new activity, or chatter post "
                    "will reset the staleness clock.</p>"
                ) % {
                    "name": lead.name or "",
                    "partner": (lead.partner_id.name if lead.partner_id else _("(no customer)")),
                    "days": self.warning_days,
                    "rule": self.name,
                    "reason": self.lost_reason_id.name,
                },
            )

    def _send_email(self, lead, partner, subject, body):
        Mail = self.env["mail.mail"].sudo()
        try:
            Mail.create({
                "subject": subject,
                "body_html": body,
                "recipient_ids": [(4, partner.id)],
                "author_id": self.env.user.partner_id.id,
                "model": "crm.lead",
                "res_id": lead.id,
            }).send()
        except Exception:
            _logger.exception(
                "StaleOpportunity: mail send failed for lead %s", lead.id,
            )

    @api.model
    def _cron_scan(self):
        """Daily cron entry point."""
        for rule in self.search([]):
            try:
                rule._run_one()
            except Exception:
                _logger.exception("StaleOpportunity rule %s failed.", rule.name)

    def action_run_now(self):
        for rule in self:
            result = rule._run_one()
            if result:
                closed, warned = result
                rule.message_post(body=_(
                    "Stale Opportunity manual run: closed %s, warned %s."
                ) % (closed, warned)) if hasattr(rule, "message_post") else None
        return True

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stale Opportunity Log"),
            "res_model": "cm_sa.stale.opportunity.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
