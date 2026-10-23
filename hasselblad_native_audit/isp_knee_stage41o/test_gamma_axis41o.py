import unittest
from gamma_axis_math41o import axis_coefficient,lerp_word,interpolate_banks


class AxisArithmetic(unittest.TestCase):
    def test_quantized_weight(self):
        self.assertEqual(axis_coefficient([0,3],1),(0,85))
        self.assertEqual(interpolate_banks([[100],[200]],[0,3],1),[133])

    def test_clamps_and_exact_internal_knot(self):
        a=[-8,4,20]
        self.assertEqual(axis_coefficient(a,-9),(0,0))
        self.assertEqual(axis_coefficient(a,4),(1,0))
        self.assertEqual(axis_coefficient(a,20),(1,256))
        self.assertEqual(axis_coefficient(a,21),(1,256))

    def test_negative_increment_floors(self):
        self.assertEqual(lerp_word(10,9,1),9)
        self.assertEqual(lerp_word(9,10,1),9)

    def test_endpoint_multiply_overflow(self):
        self.assertEqual(lerp_word(0,10000000,256),-6777216)

    def test_coefficient_shift_overflow(self):
        self.assertEqual(axis_coefficient([0,10000000],9000000),(0,-199))

    def test_duplicate_breakpoints_and_single_bank(self):
        self.assertEqual(axis_coefficient([-7,-7,3,3],-7),(1,0))
        self.assertEqual(axis_coefficient([7],100),(0,0))
        self.assertEqual(interpolate_banks([[31,47]],[7],100),[31,47])

    def test_no_bank_is_not_a_preparation_input(self):
        self.assertEqual(axis_coefficient([],10),(0,0))
        with self.assertRaises(ValueError):interpolate_banks([],[],10)

    def test_reject_unsupported_inputs(self):
        with self.assertRaises(ValueError):axis_coefficient([3,1],2)
        with self.assertRaises(ValueError):interpolate_banks([[1],[2,3]],[0,1],0)
        with self.assertRaises(ValueError):interpolate_banks([[1]],[0,1],0)


if __name__=='__main__':unittest.main()
