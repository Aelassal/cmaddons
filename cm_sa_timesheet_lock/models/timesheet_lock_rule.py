import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_MARKER = "_cm_sa_timesheet_lock_wrapper"
_ORIGINAL = "_cm_sa_timesheet_lock_original"
CTX_BYPASS = "cm_sa_timesheet_lock_bypass"
CTX_BYPASS_REASON = "cm_sa_timesheet_lock_bypass_reason"


class TimesheetBypassReasonRequired(UserError):
    """Signal the web client to ask for a mandatory bypass reason."""


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
        help=(
            "Maximum number of days in the past that an employee may log "
            "or edit a timesheet entry. Default 14."
        ),
    )
    applies_to_group_ids = fields.Many2many(
        "res.groups",
        "cm_sa_timesheet_lock_group_rel",
        "rule_id",
        "group_id",
        string="Applies to Groups",
        help=(
            "Limit the rule to members of these groups. Leave empty to "
            "apply to all employees. Members of the bypass group may only "
            "continue after entering a mandatory reason."
        ),
    )
    bypass_group_id = fields.Many2one(
        "res.groups",
        string="Bypass Group",
        help=(
            "Members of this group can override the rolling-window lock, "
            "but a mandatory reason is requested and recorded for every bypass."
        ),
    )
    error_message = fields.Char(
        default=(
            "Timesheet entries before %(earliest)s are locked. "
            "This entry's date is %(date)s (today is %(today)s; "
            "rolling window: %(max)s day(s))."
        ),
        required=True,
        help="Placeholders: %(max)s, %(date)s, %(today)s, %(earliest)s",
    )

    log_ids = fields.One2many(
        "cm_sa.timesheet.lock.log", "rule_id", readonly=True
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

        _logger.info(
            "TimesheetLock: installed create/write guards on account.analytic.line."
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
    def _build_wrapper(method, original):
        def guarded(self, *args, **kwargs):
            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)

            Rule = self.env["cm_sa.timesheet.lock.rule"].sudo()
            Log = self.env["cm_sa.timesheet.lock.log"].sudo()
            rules = Rule.search([("active", "=", True)])
            if not rules:
                return original(self, *args, **kwargs)

            today = fields.Date.context_today(self)
            user = self.env.user
            reason = (self.env.context.get(CTX_BYPASS_REASON) or "").strip()

            def get_user_groups(target_user):
                target_user = target_user.sudo()
                if "groups_id" in target_user._fields:
                    return target_user.groups_id
                if "group_ids" in target_user._fields:
                    return target_user.group_ids

                Groups = target_user.env["res.groups"].sudo()
                if "users" in Groups._fields:
                    return Groups.search([("users", "in", target_user.id)])

                target_user.env.cr.execute(
                    "SELECT gid FROM res_groups_users_rel WHERE uid = %s",
                    (target_user.id,),
                )
                return Groups.browse(
                    [row[0] for row in target_user.env.cr.fetchall()]
                )

            user_groups = get_user_groups(user)
            applicable_rules = rules.filtered(
                lambda rule: not rule.applies_to_group_ids
                or bool(rule.applies_to_group_ids & user_groups)
            )
            if not applicable_rules:
                return original(self, *args, **kwargs)

            def is_timesheet_vals(vals):
                return bool(vals.get("project_id") or vals.get("task_id"))

            def render_lock_message(rule, entry_date, earliest):
                values = {
                    "max": rule.max_days_back,
                    "date": entry_date,
                    "today": today,
                    "earliest": earliest,
                }
                try:
                    message = rule.error_message % values
                except (KeyError, TypeError, ValueError):
                    _logger.warning(
                        "Invalid placeholders in timesheet lock rule %s; "
                        "using the standard message.",
                        rule.display_name,
                    )
                    message = _(
                        "Timesheet entries before %(earliest)s are locked. "
                        "This entry's date is %(date)s (today is %(today)s; "
                        "rolling window: %(max)s day(s)).",
                        **values,
                    )

                # Existing databases may still contain the old configurable
                # message without the %(earliest)s placeholder. Always append
                # the date so the tested requirement is met after upgrade.
                if str(earliest) not in message:
                    message = _(
                        "%(message)s Earliest allowed date is %(earliest)s.",
                        message=message,
                        earliest=earliest,
                    )
                return message

            bypass_events = []

            def check_date(entry_date, source, line=False, create_index=None):
                if not entry_date:
                    return
                if isinstance(entry_date, str):
                    entry_date = fields.Date.to_date(entry_date)

                for rule in applicable_rules:
                    earliest = today - timedelta(days=rule.max_days_back)
                    if entry_date >= earliest:
                        continue

                    message = render_lock_message(rule, entry_date, earliest)
                    in_bypass_group = bool(
                        rule.bypass_group_id
                        and rule.bypass_group_id in user_groups
                    )
                    if not in_bypass_group:
                        raise UserError(message)

                    if not reason:
                        bypass_message = _(
                            "This timesheet entry is locked, but you are allowed "
                            "to bypass it. Enter a mandatory bypass reason before "
                            "saving.\n\n%(lock_message)s",
                            lock_message=message,
                        )
                        # The JS client catches this dedicated exception and
                        # displays the reason field in the same modal flow.
                        raise TimesheetBypassReasonRequired(bypass_message)

                    bypass_events.append(
                        {
                            "rule": rule,
                            "entry_date": entry_date,
                            "source": source,
                            "line": line,
                            "create_index": create_index,
                        }
                    )

            if method == "create":
                vals_list = args[0] if args else kwargs.get("vals_list", [])
                items = vals_list if isinstance(vals_list, list) else [vals_list]
                for item_index, vals in enumerate(items):
                    if not isinstance(vals, dict) or not is_timesheet_vals(vals):
                        continue
                    entry_date = (
                        vals.get("date")
                        or self.env.context.get("default_date")
                        or today
                    )
                    check_date(
                        entry_date,
                        "create",
                        create_index=item_index,
                    )
            else:
                vals = args[0] if args else kwargs.get("vals", {})
                vals = vals or {}
                for line in self:
                    is_timesheet = bool(
                        line.project_id
                        or vals.get("project_id")
                        or vals.get("task_id")
                    )
                    if not is_timesheet:
                        continue
                    entry_date = vals.get("date", line.date)
                    source = "write-new-date" if "date" in vals else "write-same-date"
                    check_date(entry_date, source, line=line)

            # Execute once with an internal context flag so Odoo's nested
            # post-processing writes do not request a second reason or create
            # duplicate log entries.
            operation_self = (
                self.with_context(**{CTX_BYPASS: True})
                if bypass_events
                else self
            )
            result = original(operation_self, *args, **kwargs)

            if bypass_events:
                if method == "create":
                    created_lines = result
                    for event in bypass_events:
                        item_index = event["create_index"]
                        line = (
                            created_lines[item_index]
                            if item_index is not None
                            and item_index < len(created_lines)
                            else False
                        )
                        Log.with_context(**{CTX_BYPASS: True}).create(
                            {
                                "rule_id": event["rule"].id,
                                "user_id": user.id,
                                "timesheet_id": line.id if line else False,
                                "entry_date": event["entry_date"],
                                "window_days": event["rule"].max_days_back,
                                "source": event["source"],
                                "reason": reason,
                            }
                        )
                else:
                    for event in bypass_events:
                        line = event["line"]
                        Log.with_context(**{CTX_BYPASS: True}).create(
                            {
                                "rule_id": event["rule"].id,
                                "user_id": user.id,
                                "timesheet_id": line.id,
                                "entry_date": event["entry_date"],
                                "window_days": event["rule"].max_days_back,
                                "source": event["source"],
                                "reason": reason,
                            }
                        )

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
