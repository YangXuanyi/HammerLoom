import unittest

from discount import apply_member_discount


class MemberDiscountTests(unittest.TestCase):
    def test_order_below_threshold_keeps_original_price(self):
        self.assertEqual(apply_member_discount(99), 99)

    def test_order_at_threshold_gets_discount(self):
        self.assertEqual(apply_member_discount(100), 90)

    def test_order_above_threshold_gets_discount(self):
        self.assertEqual(apply_member_discount(200), 180)


if __name__ == "__main__":
    unittest.main()
