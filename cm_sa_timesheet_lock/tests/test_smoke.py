"""Post-install smoke tests for cm_sa_timesheet_lock."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleSmoke(TransactionCase):
    def test_module_marked_installed(self):
        module_name = "cm_sa_timesheet_lock"
        module = self.env["ir.module.module"].search(
            [("name", "=", module_name)], limit=1
        )
        self.assertTrue(module, f"{module_name} module record missing")
        self.assertEqual(
            module.state,
            "installed",
            f"{module_name} not marked installed: {module.state}",
        )

    def test_bypass_log_has_a_mandatory_reason(self):
        reason_field = self.env["cm_sa.timesheet.lock.log"]._fields.get("reason")
        self.assertTrue(reason_field, "Bypass reason field is missing")
        self.assertTrue(reason_field.required, "Bypass reason must be required")
