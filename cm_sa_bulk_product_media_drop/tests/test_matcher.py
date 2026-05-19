from odoo.tests import TransactionCase

from ..models import matcher


class TestMatcher(TransactionCase):

    def test_is_image(self):
        self.assertTrue(matcher.is_image("foo.jpg"))
        self.assertTrue(matcher.is_image("foo.PNG"))
        self.assertFalse(matcher.is_image("foo.pdf"))
        self.assertFalse(matcher.is_image("foo"))

    def test_parse_filename_basic(self):
        p = matcher.parse_filename("SKU123.jpg")
        self.assertEqual(p["parts"], ["SKU123"])
        self.assertIsNone(p["position"])
        self.assertFalse(p["is_thumb"])

    def test_parse_filename_gallery(self):
        p = matcher.parse_filename("SKU123-2.jpg")
        self.assertEqual(p["parts"], ["SKU123"])
        self.assertEqual(p["position"], 2)

    def test_parse_filename_variant_with_gallery(self):
        p = matcher.parse_filename("SKU123-red-L-3.png")
        self.assertEqual(p["parts"], ["SKU123", "red", "L"])
        self.assertEqual(p["position"], 3)

    def test_parse_filename_thumbnail(self):
        p = matcher.parse_filename("SKU123-thumb.jpg")
        self.assertEqual(p["parts"], ["SKU123"])
        self.assertTrue(p["is_thumb"])

    def test_find_product_by_ref(self):
        parsed = matcher.parse_filename("SKU123.jpg")
        by_ref = {"sku123": 42}
        hit = matcher.find_product(parsed, by_ref, {}, [])
        self.assertIsNotNone(hit)
        self.assertEqual(hit["template_id"], 42)
        self.assertEqual(hit["match_by"], "stem")

    def test_find_product_sku_contains_dash(self):
        # Product reference 'SKU-0123' would normalize to 'sku0123' — full-stem
        # match must recognize 'SKU-0123.jpg' without the dash-split carving it up.
        parsed = matcher.parse_filename("SKU-0123.jpg")
        by_ref = {"sku0123": 99}
        hit = matcher.find_product(parsed, by_ref, {}, [])
        self.assertIsNotNone(hit)
        self.assertEqual(hit["template_id"], 99)
        self.assertEqual(hit["match_by"], "stem")

    def test_find_product_fuzzy(self):
        parsed = matcher.parse_filename("SKU0123.jpg")
        by_ref = {"sku123": 42}
        hit = matcher.find_product(parsed, by_ref, {}, [], fuzzy_threshold=0.80)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["template_id"], 42)
        self.assertEqual(hit["match_by"], "fuzzy_ref")

    def test_find_product_no_match(self):
        parsed = matcher.parse_filename("unrelated-thing.jpg")
        by_ref = {"sku123": 42}
        hit = matcher.find_product(parsed, by_ref, {}, [])
        self.assertIsNone(hit)
