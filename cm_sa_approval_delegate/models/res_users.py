import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    delegate_to_id = fields.Many2one(
        "res.users",
        string="Delegate To",
        domain="[('share', '=', False), ('active', '=', True)]",
        help="User who covers activities and approvals while you're out.",
    )
    delegation_start = fields.Date(string="Delegation Start")
    delegation_end = fields.Date(string="Delegation End")
    delegate_activities = fields.Boolean(
        string="Delegate Activities",
        default=True,
    )
    delegate_approvals = fields.Boolean(
        string="Delegate Approvals",
        default=True,
    )
    is_currently_delegating = fields.Boolean(
        compute="_compute_is_currently_delegating",
        store=False,
    )

    @api.depends("delegation_start", "delegation_end")
    def _compute_is_currently_delegating(self):
        today = fields.Date.context_today(self)
        for user in self:
            user.is_currently_delegating = bool(
                user.delegation_start
                and user.delegation_end
                and user.delegation_start <= today <= user.delegation_end
            )

    # ------------------------------------------------------------------
    # Apply / revert
    # ------------------------------------------------------------------
    def _active_delegation_log(self):
        """Return the currently-open delegation log row for this user, if any."""
        self.ensure_one()
        return self.env["cm_sa.delegation.log"].sudo().search(
            [
                ("from_user_id", "=", self.id),
                ("ended_at", "=", False),
            ],
            limit=1,
        )

    def _apply_delegation(self):
        """Reassign all open activities (and approvals if available) to
        this user's configured delegate, recording each item so revert
        is precise."""
        self.ensure_one()
        if not self.delegate_to_id:
            return False
        if self._active_delegation_log():
            return False
        Log = self.env["cm_sa.delegation.log"].sudo()
        Item = self.env["cm_sa.delegation.item"].sudo()
        log = Log.create({
            "from_user_id": self.id,
            "to_user_id": self.delegate_to_id.id,
        })

        activity_count = 0
        if self.delegate_activities:
            Activity = self.env["mail.activity"].sudo()
            activities = Activity.search([("user_id", "=", self.id)])
            for act in activities:
                Item.create({
                    "log_id": log.id,
                    "model": "mail.activity",
                    "res_id": act.id,
                    "original_user_id": self.id,
                    "delegate_user_id": self.delegate_to_id.id,
                })
                try:
                    act.write({"user_id": self.delegate_to_id.id})
                    activity_count += 1
                except Exception as exc:
                    _logger.warning(
                        "approval_delegate: activity %s reassign failed: %s",
                        act.id, exc,
                    )

        approval_count = 0
        if self.delegate_approvals and "approval.request" in self.env:
            Request = self.env["approval.request"].sudo()
            try:
                reqs = Request.search([
                    ("request_owner_id", "=", self.id),
                    ("request_status", "in", ("new", "pending")),
                ])
            except Exception:
                reqs = Request.browse([])
            # (We could also reassign the approver side; schema varies by
            #  Odoo version so we stay conservative and skip when missing.)
            for req in reqs:
                if "request_owner_id" not in req._fields:
                    continue
                Item.create({
                    "log_id": log.id,
                    "model": "approval.request",
                    "res_id": req.id,
                    "original_user_id": self.id,
                    "delegate_user_id": self.delegate_to_id.id,
                })
                try:
                    req.write({"request_owner_id": self.delegate_to_id.id})
                    approval_count += 1
                except Exception as exc:
                    _logger.warning(
                        "approval_delegate: approval %s reassign failed: %s",
                        req.id, exc,
                    )

        log.write({
            "reassigned_activity_count": activity_count,
            "reassigned_approval_count": approval_count,
        })
        try:
            self.message_post(
                body=_(
                    "Delegation started to <b>%(to)s</b>. "
                    "Reassigned %(a)s activity(ies) and %(ap)s approval(s)."
                ) % {
                    "to": self.delegate_to_id.display_name,
                    "a": activity_count,
                    "ap": approval_count,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass
        return log

    def _revert_delegation(self):
        """Reverse every not-yet-reverted item in this user's open log."""
        self.ensure_one()
        log = self._active_delegation_log()
        if not log:
            return False
        Item = self.env["cm_sa.delegation.item"].sudo()
        items = Item.search([("log_id", "=", log.id), ("reverted", "=", False)])
        for item in items:
            if item.model not in self.env:
                continue
            try:
                rec = self.env[item.model].sudo().browse(item.res_id)
                if not rec.exists():
                    continue
                if item.model == "mail.activity":
                    rec.write({"user_id": item.original_user_id.id})
                elif item.model == "approval.request":
                    if "request_owner_id" in rec._fields:
                        rec.write({"request_owner_id": item.original_user_id.id})
                item.write({
                    "reverted": True,
                    "reverted_at": fields.Datetime.now(),
                })
            except Exception as exc:
                _logger.warning(
                    "approval_delegate: revert of %s/%s failed: %s",
                    item.model, item.res_id, exc,
                )
        log.write({
            "ended_at": fields.Datetime.now(),
            "auto_reversed": True,
        })
        try:
            self.message_post(
                body=_(
                    "Delegation to <b>%s</b> ended; items reverted."
                ) % log.to_user_id.display_name,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_process_delegations(self):
        today = fields.Date.context_today(self)
        # Activate
        to_activate = self.sudo().search([
            ("delegate_to_id", "!=", False),
            ("delegation_start", "<=", today),
            ("delegation_end", ">=", today),
        ])
        for user in to_activate:
            if not user._active_delegation_log():
                try:
                    user._apply_delegation()
                except Exception:
                    _logger.exception(
                        "approval_delegate: apply failed for user %s",
                        user.id,
                    )
        # Deactivate
        Log = self.env["cm_sa.delegation.log"].sudo()
        open_logs = Log.search([("ended_at", "=", False)])
        for log in open_logs:
            user = log.from_user_id
            expired = (
                not user.delegation_end
                or user.delegation_end < today
                or not user.delegate_to_id
            )
            if expired:
                try:
                    user._revert_delegation()
                except Exception:
                    _logger.exception(
                        "approval_delegate: revert failed for user %s",
                        user.id,
                    )

    # ------------------------------------------------------------------
    # Manual button
    # ------------------------------------------------------------------
    def action_end_delegation_now(self):
        for user in self:
            user._revert_delegation()
        return True
