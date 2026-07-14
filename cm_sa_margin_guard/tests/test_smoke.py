"""Installation smoke tests for cm_sa_margin_guard."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleSmoke(TransactionCase):
    def test_module_marked_installed(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "cm_sa_margin_guard")], limit=1
        )
        self.assertTrue(module, "cm_sa_margin_guard module record missing")
        self.assertEqual(
            module.state,
            "installed",
            f"cm_sa_margin_guard not marked installed: {module.state}",
        )
