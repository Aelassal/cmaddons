from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.margin_guard_rule import CTX_AUDIT_CREATE


@tagged("post_install", "-at_install")
class TestMarginGuard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_model = cls.env["ir.model"]._get("sale.order")
        cls.manager_group = cls.env.ref("sales_team.group_sale_manager")
        cls.internal_group = cls.env.ref("base.group_user")
        cls.partner = cls.env["res.partner"].create(
            {"name": "Margin Guard Test Customer"}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Margin Guard Test Product",
                "list_price": 100.0,
                "standard_price": 20.0,
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Margin Override Manager",
                "login": "margin.override.manager.test",
                "email": "margin.override.manager.test@example.com",
                "company_id": cls.env.company.id,
                "company_ids": [Command.set([cls.env.company.id])],
                "group_ids": [
                    Command.set([cls.internal_group.id, cls.manager_group.id])
                ],
            }
        )

    def _create_order(self, price):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "name": self.product.display_name,
                            "product_id": self.product.id,
                            "product_uom": self.product.uom_id.id,
                            "product_uom_qty": 1.0,
                            "price_unit": price,
                        }
                    )
                ],
            }
        )

    def _create_rule(self, **overrides):
        values = {
            "name": "Test dynamic margin rule",
            "model_id": self.sale_model.id,
            "method_name": "action_confirm",
            "margin_formula": "record.amount_untaxed",
            "threshold_pct": 50.0,
            "domain": "[]",
            "override_group_id": self.manager_group.id,
            "require_reason_on_override": True,
            "min_reason_length": 10,
            "error_message": (
                "%(model)s is below margin: "
                "%(actual).1f%% < %(threshold).1f%%"
            ),
        }
        values.update(overrides)
        return self.env["cm_sa.margin.guard.rule"].create(values)

    def test_error_message_is_validated_on_rule_save(self):
        with self.assertRaises(ValidationError):
            self._create_rule(
                name="Invalid error message rule",
                error_message="Invalid placeholder %(unknown)s",
            )

    def test_override_log_is_immutable(self):
        rule = self._create_rule(name="Immutable log rule")
        log = self.env["cm_sa.margin.override.log"].sudo().with_context(
            **{CTX_AUDIT_CREATE: True}
        ).create(
            {
                "rule_id": rule.id,
                "res_model": "sale.order",
                "res_id": 999999,
                "record_name": "SO-AUDIT-TEST",
                "user_id": self.manager.id,
                "threshold_pct": 10.0,
                "actual_pct": 5.0,
                "reason": "Original approved reason",
            }
        )

        with self.assertRaises(AccessError):
            log.with_user(self.manager).write({"reason": "Changed reason"})
        with self.assertRaises(AccessError):
            log.with_user(self.manager).unlink()

    def test_mixed_batch_confirms_safe_and_requests_only_required_override(self):
        self._create_rule(name="Mixed batch rule")
        safe_order = self._create_order(100.0)
        low_margin_order = self._create_order(10.0)

        selected = (safe_order | low_margin_order).with_user(self.manager)
        action = selected.action_confirm()

        self.assertEqual(safe_order.state, "sale")
        self.assertEqual(low_margin_order.state, "draft")
        self.assertEqual(action.get("res_model"), "cm_sa.margin.override.wizard")
        self.assertEqual(
            action["context"]["default_record_id_str"],
            str(low_margin_order.id),
        )

        defaults = {
            key.removeprefix("default_"): value
            for key, value in action["context"].items()
            if key.startswith("default_")
        }
        defaults["reason"] = "Approved for strategic customer"
        wizard = self.env["cm_sa.margin.override.wizard"].with_user(
            self.manager
        ).create(defaults)
        wizard.action_confirm_override()

        self.assertEqual(low_margin_order.state, "sale")
        log = self.env["cm_sa.margin.override.log"].search(
            [("res_model", "=", "sale.order"), ("res_id", "=", low_margin_order.id)]
        )
        self.assertEqual(len(log), 1)
        self.assertEqual(log.user_id, self.manager)
        self.assertEqual(log.reason, "Approved for strategic customer")
