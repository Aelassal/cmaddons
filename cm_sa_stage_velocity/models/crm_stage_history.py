import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_MARKER = "_cm_sa_stage_velocity_wrapper"
_ORIGINAL = "_cm_sa_stage_velocity_original"
CTX_BYPASS = "cm_sa_stage_velocity_bypass"


class CmSaCrmStageHistory(models.Model):
    _name = "cm_sa.crm.stage.history"
    _description = "CRM Stage History"
    _order = "entered_at desc, id desc"
    _rec_name = "lead_id"

    lead_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        ondelete="cascade",
        index=True,
    )
    stage_id = fields.Many2one(
        "crm.stage",
        string="Stage",
        required=True,
        ondelete="restrict",
        index=True,
    )
    user_id = fields.Many2one(
        related="lead_id.user_id",
        store=True, readonly=True, index=True,
        string="Salesperson",
    )
    team_id = fields.Many2one(
        related="lead_id.team_id",
        store=True, readonly=True, index=True,
        string="Sales Team",
    )
    partner_id = fields.Many2one(
        related="lead_id.partner_id", store=True, readonly=True,
    )
    company_currency = fields.Many2one(
        related="lead_id.company_currency", store=True, readonly=True,
    )
    expected_revenue = fields.Monetary(
        related="lead_id.expected_revenue", store=True, readonly=True,
        currency_field="company_currency",
    )
    entered_at = fields.Datetime(
        required=True, default=fields.Datetime.now, index=True,
    )
    exited_at = fields.Datetime(
        help="When the lead left this stage. Null = currently in stage.",
    )
    days_in_stage = fields.Float(
        compute="_compute_days_in_stage", store=True, index=True,
    )
    is_current = fields.Boolean(
        compute="_compute_is_current", store=True, index=True,
    )

    @api.depends("entered_at", "exited_at")
    def _compute_days_in_stage(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.entered_at:
                rec.days_in_stage = 0.0
                continue
            end = rec.exited_at or now
            rec.days_in_stage = (end - rec.entered_at).total_seconds() / 86400.0

    @api.depends("exited_at")
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = not rec.exited_at

    def action_open_lead(self):
        self.ensure_one()
        if not self.lead_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Registry hook — wrap crm.lead.create + write to auto-log
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        if not self._table_exists():
            return
        if "crm.lead" not in self.env.registry:
            return
        cls = type(self.env["crm.lead"])
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
        _logger.info("StageVelocity: installed wrappers on crm.lead.")

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
        def wrapped(self, *args, **kwargs):
            if self.env.context.get(CTX_BYPASS):
                return original(self, *args, **kwargs)
            History = self.env["cm_sa.crm.stage.history"].sudo()
            now = fields.Datetime.now()

            if method == "create":
                res = original(self, *args, **kwargs)
                # res is a recordset of newly-created leads
                try:
                    for lead in res:
                        if lead.stage_id:
                            History.with_context(**{CTX_BYPASS: True}).create({
                                "lead_id": lead.id,
                                "stage_id": lead.stage_id.id,
                                "entered_at": now,
                            })
                except Exception:
                    _logger.exception(
                        "StageVelocity: create-time history write failed"
                    )
                return res

            # method == "write"
            vals = args[0] if args else kwargs.get("vals", {})
            new_stage_id = vals.get("stage_id") if isinstance(vals, dict) else None
            if not new_stage_id:
                return original(self, *args, **kwargs)
            # Snapshot prior stage per lead before the write applies.
            prior = {lead.id: lead.stage_id.id if lead.stage_id else False
                     for lead in self}
            res = original(self, *args, **kwargs)
            try:
                for lead in self:
                    was = prior.get(lead.id)
                    becomes = new_stage_id
                    if was == becomes:
                        continue
                    # Close the open history row for (lead, was).
                    if was:
                        open_rows = History.search([
                            ("lead_id", "=", lead.id),
                            ("stage_id", "=", was),
                            ("exited_at", "=", False),
                        ], limit=1)
                        if open_rows:
                            open_rows.write({"exited_at": now})
                    # Open a new history row for (lead, becomes).
                    if becomes:
                        History.with_context(**{CTX_BYPASS: True}).create({
                            "lead_id": lead.id,
                            "stage_id": becomes,
                            "entered_at": now,
                        })
            except Exception:
                _logger.exception(
                    "StageVelocity: write-time history write failed"
                )
            return res

        return wrapped
