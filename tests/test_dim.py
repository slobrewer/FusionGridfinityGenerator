# Run from the repo root:  python3 -m unittest discover -s tests
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib', 'gridfinityUtils'))

from dim import Dim, DimPoint, dmax, dmin, dtan, LENGTH, UNITLESS, ANGLE, literalExpression  # noqa: E402


class LiteralTests(unittest.TestCase):
    def test_length_literal_is_mm(self):
        self.assertEqual(literalExpression(0.475, LENGTH), '4.75 mm')
        self.assertEqual(literalExpression(4.2, LENGTH), '42 mm')
        self.assertEqual(literalExpression(-0.025, LENGTH), '-0.25 mm')
        self.assertEqual(literalExpression(0, LENGTH), '0 mm')

    def test_unitless_and_angle_literals(self):
        self.assertEqual(literalExpression(5.0, UNITLESS), '5')
        self.assertEqual(literalExpression(2.5, UNITLESS), '2.5')
        self.assertEqual(literalExpression(0.7853981633974483, ANGLE), '45 deg')


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.binHeight = Dim.named('gfb1_bin_height_u', 5, UNITLESS)
        self.heightUnit = Dim.named('gfb1_height_unit', 0.7, LENGTH)

    def test_bin_body_height_chain(self):
        withoutBase = self.binHeight - 1
        total = withoutBase * self.heightUnit + dmax(0, self.heightUnit - 0.475)
        self.assertAlmostEqual(total.value, 3.025)
        self.assertEqual(total.kind, LENGTH)
        self.assertEqual(total.expr, '(gfb1_bin_height_u - 1) * gfb1_height_unit + max(0 mm; gfb1_height_unit - 4.75 mm)')

    def test_plain_number_in_sum_takes_dim_unit(self):
        self.assertEqual((self.heightUnit + 0.1).expr, 'gfb1_height_unit + 1 mm')
        self.assertEqual((self.binHeight + 1).expr, 'gfb1_bin_height_u + 1')

    def test_plain_number_in_product_is_scale(self):
        self.assertEqual((self.heightUnit * 2).expr, 'gfb1_height_unit * 2')
        self.assertEqual((2 * self.heightUnit).expr, '2 * gfb1_height_unit')
        self.assertEqual((self.heightUnit / 2).kind, LENGTH)

    def test_parentheses(self):
        a = self.heightUnit - 0.1
        self.assertEqual((0.5 - a).expr, '5 mm - (gfb1_height_unit - 1 mm)')
        self.assertEqual((a * 3).expr, '(gfb1_height_unit - 1 mm) * 3')
        self.assertEqual((self.heightUnit + (-0.1)).expr, 'gfb1_height_unit + (-1 mm)')
        self.assertEqual((-a).expr, '-(gfb1_height_unit - 1 mm)')
        self.assertAlmostEqual((-a).value, -0.6)

    def test_division_of_lengths_is_unitless(self):
        self.assertEqual((self.heightUnit / self.heightUnit).kind, UNITLESS)

    def test_min_max(self):
        depth = dmin(self.heightUnit * 4, 2.0)
        self.assertEqual(depth.expr, 'min(gfb1_height_unit * 4; 20 mm)')
        self.assertAlmostEqual(depth.value, 2.0)
        self.assertEqual(dmax(1.0, 2.0), 2.0)  # floats stay floats

    def test_comparisons_and_float(self):
        self.assertTrue(self.heightUnit < 1)
        self.assertTrue(self.heightUnit > 0.5)
        self.assertEqual(float(self.heightUnit), 0.7)

    def test_point_holds_dims(self):
        point = DimPoint(0, 0, self.heightUnit * 2)
        self.assertEqual(point.z.expr, 'gfb1_height_unit * 2')

    def test_identities_keep_expressions_short(self):
        self.assertIs(self.heightUnit + 0, self.heightUnit)
        self.assertIs(0 + self.heightUnit, self.heightUnit)
        self.assertIs(self.heightUnit - 0, self.heightUnit)
        self.assertEqual((0 - self.heightUnit).expr, '-gfb1_height_unit')
        self.assertIs(self.heightUnit * 1, self.heightUnit)
        self.assertIs(1 * self.heightUnit, self.heightUnit)
        self.assertIs(self.heightUnit / 1, self.heightUnit)
        self.assertEqual((1 / self.binHeight).expr, '1 / gfb1_bin_height_u')
        self.assertEqual(0 * self.heightUnit, 0.0)
        self.assertIs(self.heightUnit - 0 * self.heightUnit, self.heightUnit)

    def test_tab_width_with_tangent(self):
        angle = Dim.named('gfb1_tab_angle', math.radians(45), ANGLE)
        width = Dim.named('gfb1_tab_width', 1.3, LENGTH)
        actual = width + Dim.cm(0.06) / dtan((math.radians(90) - angle) / 2)
        self.assertEqual(actual.expr, 'gfb1_tab_width + (0.6 mm / tan((90 deg - gfb1_tab_angle) / 2))')
        self.assertAlmostEqual(actual.value, 1.3 + 0.06 / math.tan(math.radians(22.5)))
        self.assertEqual(dtan(0.5), math.tan(0.5))

    def test_double_negation_and_abs(self):
        offset = self.heightUnit - 0.1
        self.assertIs(-(-offset), offset)
        self.assertEqual(abs(-offset).expr, 'gfb1_height_unit - 1 mm')
        self.assertEqual(abs(0 - self.heightUnit).expr, 'gfb1_height_unit')
        self.assertIs(abs(offset), offset)


if __name__ == '__main__':
    unittest.main()
