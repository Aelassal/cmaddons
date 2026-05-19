from odoo import _, api, fields, models

# Partner fields we allow in the cascade picker. Only fields that make
# sense to propagate from a company to its contacts: postal address,
# identifiers, and common contact lines. We intentionally exclude
# name, relational fields tied to accounting / sales, and ``parent_id``.
DEFAULT_WATCHED_FIELDS = [
    "street", "street2", "city", "zip",
    "country_id", "state_id",
    "email", "phone", "mobile", "website",
    "vat", "lang",
]


class CmSaCascadeSetting(models.Model):
    _name = "cm_sa.cascade.setting"
    _description = "Partner Cascade Settings"
    _rec_name = "name"

    name = fields.Char(default="Default", required=True)
    active = fields.Boolean(default=True)

    watched_field_ids = fields.Many2many(
        "ir.model.fields",
        "cm_sa_cascade_setting_field_rel",
        "setting_id",
        "field_id",
        string="Watched Fields",
        domain="[('model', '=', 'res.partner'), ('name', 'in', "
               + repr(DEFAULT_WATCHED_FIELDS)
               + ")]",
        help="Fields that, when changed on a company partner, trigger a "
             "cascade proposal to the children.",
    )

    @api.model
    def _get_default_setting(self):
        """Return the first active setting row, or create one on the fly."""
        setting = self.search([("active", "=", True)], limit=1)
        if setting:
            return setting
        return self.sudo().create({"name": "Default"})

    @api.model
    def _watched_field_names(self):
        """Names of fields the current setting watches; empty list if none."""
        setting = self._get_default_setting()
        return setting.watched_field_ids.mapped("name")
