import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_MARKER = "_cm_sa_timesheet_lock_wrapper"
_ORIGINAL = "_cm_sa_timesheet_lock_original"
CTX_BYPASS = "cm_sa_timesheet_lock_bypass"
CTX_BYPASS_REASON = "cm_sa_timesheet_lock_bypass_reason"
REASON_FIELD = "cm_sa_timesheet_bypass_reason"


class CmSaTimesheetLockRule(models.Model):
    _name = "cm_sa.timesheet.lock.rule"
    _description = "Timesheet Back-Dating Lock Rule"
    _order = "name, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    max_days_back = fields.Integer(
        default=14,
        required=True,
        help="Maximum number of days in the past that an employee may log "
             "or edit a timesheet entry. Default 14.",
    )
    applies_to_group_ids = fields.Many2many(
        "res.groups",
        "cm_sa_timesheet_lock_group_rel",
        "rule_id",
        "group_id",
        string="Applies to Groups",
        help="Limit the rule to members of these groups. Leave empty to "
             "apply to all employees. Admins / bypass group always override.",
    )
    bypass_group_id = fields.Many2one(
        "res.groups",
        string="Bypass Group",
        help="Members of this group can back-date past the window only after "
             "entering a mandatory bypass reason. Every bypass is logged.",
    )
    error_message = fields.Char(
        default="Timesheet entries older than %(max)s day(s) are locked. "
                "This entry's date is %(date)s. "
                "Earliest allowed date is %(earliest)s. "
                "Today is %(today)s.",
        required=True,
        help="Placeholders: %(max)s, %(date)s, %(earliest)s, %(today)s",
    )

    log_ids = fields.One2many(
        "cm_sa.timesheet.lock.log",
        "rule_id",
        readonly=True,
    )
    log_count = fields.Integer(compute="_compute_log_count")

    _name_unique = models.Constraint(
        "unique(name)",
        "A timesheet-lock rule with this name already exists.",
    )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.constrains("max_days_back")
    def _check_max_days(self):
        for rec in self:
            if rec.max_days_back <= 0:
                raise ValidationError(_("Max Days Back must be > 0."))

    # ------------------------------------------------------------------
    # Registry hook
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return
        if "account.analytic.line" not in self.env.registry:
            return
        cls = type(self.env["account.analytic.line"])
        for method in ("create", "write"):
            original = getattr(cls, method, None)
            if original is None:
                continue
            if getattr(original, _MARKER, False):
                original = getattr(original, _ORIGINAL, original)
            wrapper = self._build_wrapper(method, original)
            setattr(wrapper, _MARKER, True)
            setattr(wrapper, _ORIGINAL, original)
            wrapper.__name__ = method
            wrapper.__qualname__ = f"{cls.__name__}.{method}"
            setattr(cls, method, wrapper)
        _logger.info("TimesheetLock: installed wrappers on account.analytic.line.")

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
    def _build_wrapper(method, original):
        def guarded(self, *args, **kwargs):
            Rule = self.env["cm_sa.timesheet.lock.rule"].sudo()
            Log = self.env["cm_sa.timesheet.lock.log"].sudo()

            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            rules = Rule.search([("active", "=", True)])
            if not rules:
                return original(self, *args, **kwargs)

            today = fields.Date.context_today(self)

            def get_user_groups(user):
                user = user.sudo()

                if "groups_id" in user._fields:
                    return user.groups_id
                if "group_ids" in user._fields:
                    return user.group_ids

                Groups = user.env["res.groups"].sudo()
                if "users" in Groups._fields:
                    return Groups.search([("users", "in", user.id)])

                user.env.cr.execute(
                    "SELECT gid FROM res_groups_users_rel WHERE uid = %s",
                    (user.id,),
                )
                return Groups.browse([row[0] for row in user.env.cr.fetchall()])

            def applicable_rules_for_user(user):
                user_groups = get_user_groups(user)
                out = []
                for rule in rules:
                    if (
                        rule.applies_to_group_ids
                        and not (rule.applies_to_group_ids & user_groups)
                    ):
                        continue
                    out.append(rule)
                return out

            def build_error_message(rule, rule_date, cutoff):
                values = {
                    "max": rule.max_days_back,
                    "date": rule_date,
                    "earliest": cutoff,
                    "today": today,
                }
                try:
                    return rule.error_message % values
                except Exception:
                    _logger.exception(
                        "TimesheetLock: invalid error_message placeholders on rule %s",
                        rule.id,
                    )
                    return _(
                        "Timesheet entries older than %(max)s day(s) are locked. "
                        "This entry's date is %(date)s. "
                        "Earliest allowed date is %(earliest)s. "
                        "Today is %(today)s."
                    ) % values

            def normalize_reason(reason):
                if reason is None:
                    return False
                reason = str(reason).strip()
                return reason or False

            def check_date(rule_date, context_source, bypass_reason=False, line=False):
                """Validate one timesheet date and return pending bypass log rows."""
                if not rule_date:
                    return []
                if isinstance(rule_date, str):
                    rule_date = fields.Date.to_date(rule_date)

                pending_logs = []
                applicable = applicable_rules_for_user(self.env.user)
                user_groups = get_user_groups(self.env.user)
                stored_reason = False
                if line and REASON_FIELD in line._fields:
                    stored_reason = line[REASON_FIELD]
                bypass_reason = normalize_reason(
                    bypass_reason
                    or self.env.context.get(CTX_BYPASS_REASON)
                    or stored_reason
                )

                for rule in applicable:
                    cutoff = today - timedelta(days=rule.max_days_back)
                    if rule_date >= cutoff:
                        continue  # within window

                    in_bypass = (
                        rule.bypass_group_id
                        and rule.bypass_group_id in user_groups
                    )
                    if not in_bypass:
                        raise UserError(build_error_message(rule, rule_date, cutoff))

                    if not bypass_reason:
                        raise UserError(_(
                            "This timesheet entry is locked, but you are allowed "
                            "to bypass it. Please enter a mandatory bypass reason."
                        ))

                    pending_logs.append({
                        "rule_id": rule.id,
                        "user_id": self.env.user.id,
                        "line_id": line.id if line else False,
                        "entry_date": rule_date,
                        "window_days": rule.max_days_back,
                        "source": context_source,
                        "reason": bypass_reason,
                    })

                return pending_logs

            pending_logs = []
            records_to_clear_reason = self.env["account.analytic.line"]

            if method == "create":
                vals_list = args[0] if args else kwargs.get("vals_list", [])
                items = vals_list if isinstance(vals_list, list) else [vals_list]

                # Validate first. The actual log rows are created after the
                # timesheet lines are successfully created, so line_id can be set.
                pending_logs_by_index = []
                for vals in items:
                    vals = vals or {}
                    reason = vals.get(REASON_FIELD)
                    logs = []
                    if "date" in vals:
                        logs = check_date(vals.get("date"), "create", reason)
                    pending_logs_by_index.append(logs)

                records = original(self, *args, **kwargs)

                for record, logs in zip(records, pending_logs_by_index):
                    for log_vals in logs:
                        log_vals["line_id"] = record.id
                        pending_logs.append(log_vals)
                    if logs and record[REASON_FIELD]:
                        records_to_clear_reason |= record

                if pending_logs:
                    try:
                        Log.with_context(**{CTX_BYPASS: True}).create(pending_logs)
                    except Exception:
                        _logger.exception("TimesheetLock: bypass log failed")

                if records_to_clear_reason:
                    records_to_clear_reason.with_context(**{CTX_BYPASS: True}).write({
                        REASON_FIELD: False,
                    })

                return records

            # write
            vals = args[0] if args else kwargs.get("vals", {})
            vals = vals or {}
            bypass_reason = vals.get(REASON_FIELD)

            if "date" in vals:
                new_date = vals.get("date")
                for line in self:
                    pending_logs.extend(
                        check_date(new_date, "write-new-date", bypass_reason, line)
                    )
                    if pending_logs and bypass_reason:
                        records_to_clear_reason |= line
            else:
                for line in self:
                    line_logs = check_date(
                        line.date,
                        "write-same-date",
                        bypass_reason,
                        line,
                    )
                    pending_logs.extend(line_logs)
                    if line_logs and bypass_reason:
                        records_to_clear_reason |= line

            result = original(self, *args, **kwargs)

            if pending_logs:
                try:
                    Log.with_context(**{CTX_BYPASS: True}).create(pending_logs)
                except Exception:
                    _logger.exception("TimesheetLock: bypass log failed")

            if records_to_clear_reason:
                records_to_clear_reason.with_context(**{CTX_BYPASS: True}).write({
                    REASON_FIELD: False,
                })

            return result

        return guarded

    def _signal_registry(self):
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.debug("TimesheetLock: registry signal unavailable")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._signal_registry()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {
            "active",
            "max_days_back",
            "applies_to_group_ids",
            "bypass_group_id",
            "error_message",
        }.intersection(vals):
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
            "res_model": "cm_sa.timesheet.lock.log",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
        }
