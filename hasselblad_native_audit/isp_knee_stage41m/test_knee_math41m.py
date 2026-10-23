import unittest
from knee_math41m import knee_slopes,fusion_table,sdiv32


class KneePreparationTests(unittest.TestCase):
    def test_fractional_and_descending_slopes(self):
        self.assertEqual(knee_slopes([0,1],[0,3]),[1365,0])
        self.assertEqual(knee_slopes([4,1],[0,2]),[-6144,0])

    def test_machine_integer_edges(self):
        self.assertEqual(knee_slopes([1,10],[7,7]),[0,0])
        self.assertEqual(knee_slopes([0,524288],[0,1]),[-2147483648,0])
        self.assertEqual(sdiv32(-2147483648,-1),-2147483648)

    def test_domain_checks(self):
        with self.assertRaises(ValueError):knee_slopes([0],[0])
        with self.assertRaises(ValueError):fusion_table([0]*256,[0]*257,1024)
        with self.assertRaises(ValueError):fusion_table([0]*257,[0]*257,4097)

    def test_fusion_identity_half_gain_and_endpoint(self):
        ramp=list(range(257))
        self.assertEqual(fusion_table(ramp,ramp,1024),ramp)
        self.assertEqual(fusion_table(ramp,ramp,512),[i//2 for i in ramp])
        self.assertEqual(fusion_table(ramp,ramp,4096),[min(i*4,256) for i in ramp])

    def test_float32_operation_order(self):
        table=[0]*257;table[65]=37392;table[66]=-31519
        self.assertEqual(fusion_table(table,[99]*257,677),[6234]*257)
        self.assertEqual(int(37392+(677*99/1024-65)*(-31519-37392)),6233)

    def test_unsigned_output_saturation(self):
        self.assertEqual(fusion_table([-12]*257,[99]*257,1024),[0]*257)


if __name__=='__main__':unittest.main()
