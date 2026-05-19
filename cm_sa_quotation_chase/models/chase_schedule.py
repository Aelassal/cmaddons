from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ChaseSchedule(models.Model):
    _name = "cm_sa.chase.schedule"
    _description = "Quotation Chase Schedule"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(
        help="Internal notes — what this schedule is for, when to use it.",
    )
    step_ids = fields.One2many(
        "cm_sa.chase.step",
        "schedule_id",
        string="Steps",
        copy=True,
    )
    step_count = fields.Integer(compute="_compute_step_count")

    @api.depends("step_ids")
    def _compute_step_count(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)


class ChaseStep(models.Model):
    _name = "cm_sa.chase.step"
    _description = "Quotation Chase Step"
    _order = "sequence, days_after_send"

    schedule_id = fields.Many2one(
        "cm_sa.chase.schedule",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10, required=True)
    days_after_send = fields.Integer(
        string="Days after send",
        required=True,
        default=3,
        help="Fire this chase when the base date (last chase, or quotation date) "
             "is at least this many days in the past.",
    )
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Mail Template",
        required=True,
        domain="[('model', '=', 'sale.order')]",
        help="Email template rendered against the sale order and sent to the customer.",
    )

    @api.constrains("days_after_send")
    def _check_days_after_send(self):
        for rec in self:
            if rec.days_after_send < 0:
                raise ValidationError(_("Days after send must be zero or positive."))
