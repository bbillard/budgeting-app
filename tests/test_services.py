import unittest

from services import parse_amount


class TestServices(unittest.TestCase):
    def test_parse_amount_euro_format(self):
        self.assertEqual(parse_amount("1 234,56 €"), 1234.56)


if __name__ == '__main__':
    unittest.main()
