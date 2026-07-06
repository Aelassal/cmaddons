from odoo import models

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        # Remove or fake the expiration info so the UI never blocks
        result.pop('expiration_date', None)
        result.pop('expiration_reason', None)
        result.pop('warning', None)
        return result 