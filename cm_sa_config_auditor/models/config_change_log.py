from odoo import fields, models


class CmSaConfigChangeLog(models.Model):
    _name = "cm_sa.config.change.log"
    _description = "Config Parameter Change Log"
    _order = "create_date desc, id desc"
    _rec_name = "key"

    key = fields.Char(required=True, index=True)
    change_type = fields.Selection(
        [("create", "Create"), ("write", "Write"), ("unlink", "Unlink")],
        required=True,
    )
    old_value = fields.Text()
    new_value = fields.Text()
    user_id = fields.Many2one(
        "res.users",
        string="Changed By",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user,
        index=True,
    )
    is_sensitive = fields.Boolean(
        default=False,
        help="True when this key is on the sensitive-key watch list at the "
             "time of the change.",
    )
