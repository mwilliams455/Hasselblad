"""Numerical and geometric checks for the offline comparison harness."""
import unittest
import cv2
import numpy as np
from compare_hasselblad_pairs41j import half_crop, orient, srgb_encode, srgb_decode, fit_exposure, registration


class ComparisonTests(unittest.TestCase):
    def test_srgb_roundtrip_and_known_breakpoints(self):
        x=np.linspace(0,1,1001)
        np.testing.assert_allclose(srgb_decode(srgb_encode(x)),x,atol=1e-14)
        self.assertAlmostEqual(float(srgb_encode(np.array(.003))),.03876)
        self.assertAlmostEqual(float(srgb_encode(np.array(1.))),1.)

    def test_crop_before_orientation(self):
        a=np.arange(8*10).reshape(8,10)
        cropped=half_crop(a,(4,2),(8,6))
        np.testing.assert_array_equal(cropped,np.array([[12,13,14,15],[22,23,24,25],[32,33,34,35]]))
        rotated=orient(cropped,8)
        self.assertEqual(rotated.shape,(4,3))
        np.testing.assert_array_equal(rotated[0],[15,25,35])

    def test_invalid_crop_rejected(self):
        with self.assertRaises(AssertionError): half_crop(np.zeros((4,4)),(1,0),(4,4))
        with self.assertRaises(AssertionError): half_crop(np.zeros((4,4)),(6,0),(4,4))

    def test_recover_known_exposure(self):
        rng=np.random.default_rng(41)
        x=rng.uniform(.001,.3,(80,80,3)).astype(np.float32)
        reference=srgb_encode(x*2**1.25)
        fit=fit_exposure(x,reference,np.ones((80,80),bool))
        self.assertAlmostEqual(fit,1.25,places=5)

    def test_registration_direction_and_subpixel_translation(self):
        rng=np.random.default_rng(41)
        texture=rng.random((360,480),dtype=np.float32)
        texture=cv2.GaussianBlur(texture,(0,0),1)
        image=np.repeat(texture[:,:,None],3,axis=2)
        known=np.float32([[1,0,3.2],[0,1,-2.4]])
        target=cv2.warpAffine(image,known,(480,360))
        warp,info=registration(image,target)
        np.testing.assert_allclose(warp[:,2],known[:,2],atol=.12)
        self.assertGreater(info['inliers'],30)


if __name__=='__main__': unittest.main()
