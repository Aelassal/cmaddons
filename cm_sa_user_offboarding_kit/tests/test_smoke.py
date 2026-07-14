"""Smoke test for cm_sa_user_offboarding_kit.

Protects the module against install-time regressions: a backport that
drops a required field, a syntax error in a data XML, or a missing
dependency will fail this test loud. Runs post-install.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleSmoke(TransactionCase):
    def test_module_marked_installed(self):
        """After post-install, the module record must be in state 'installed'."""
        mod = self.env["ir.module.module"].search([("name", "=", "cm_sa_user_offboarding_kit")])
        self.assertTrue(mod, "cm_sa_user_offboarding_kit module record missing")
        self.assertEqual(mod.state, "installed",
                         f"cm_sa_user_offboarding_kit not marked installed: {mod.state}")
