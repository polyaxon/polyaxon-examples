from decimal import Decimal
import unittest

from amounts import parse_amount


class AmountTests(unittest.TestCase):
    def test_grouped_amount(self):
        self.assertEqual(parse_amount("$1,234.50"), Decimal("1234.50"))

    def test_exact_decimal(self):
        self.assertIsInstance(parse_amount("12.30"), Decimal)
        self.assertEqual(parse_amount("12.30"), Decimal("12.30"))

    def test_whitespace(self):
        self.assertEqual(parse_amount("  $0.05  "), Decimal("0.05"))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_amount("not an amount")


if __name__ == "__main__":
    unittest.main()
