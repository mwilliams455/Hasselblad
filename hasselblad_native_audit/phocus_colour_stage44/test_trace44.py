#!/usr/bin/env python3
"""Synthetic diagnostics checks. No owner photo/profile/APK is required."""
import tempfile,unittest
from pathlib import Path
import numpy as np
from audit_colour44 import Core,trace,diff
class TraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.core=Core(Path(cls.tmp.name)/'core.so')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_trace_matches_core_at_boundaries(self):
        rng=np.random.default_rng(44)
        pixels=np.vstack([np.zeros((1,3)),np.full((1,3),65535),np.eye(3)*65535,rng.integers(0,65536,(2000,3))]).astype(np.uint16)
        first=np.array([[.25,.65,.1],[-.2,-.3,.5],[.5,-.4,-.1]])
        second=np.linalg.inv(first);gy,gx=np.mgrid[:89,:105]
        grid=np.stack([gx-20+np.sin(gy/9),gy-32+np.sin(gx/11)],-1)
        curve=np.floor((np.arange(65536)/65536)**.4547*65536).clip(0,65535).astype(np.float32)
        for exposure in (.0625,1,16):
            p=self.core.params(first,second,grid,False,curve,[15500,1e-9,-1e-5,.8],exposure=exposure)
            actual=self.core.render(pixels,p);traced,_,stats=trace(pixels,p,np.eye(3),1/.4547)
            np.testing.assert_array_equal(actual,traced)
            self.assertGreater(stats['lut_coordinate_clamped_pixels'],0)
    def test_clipping_stage_counts_and_black_bypass(self):
        curve=np.arange(65536,dtype=np.float32);curve[0]=10
        first=np.zeros((3,3));first[0,0]=1
        p=self.core.params(first,np.zeros((3,3)),np.zeros((2,2,2)),False,curve,[2,0,0,1],exposure=2)
        pixels=np.array([[40000,0,0],[0,1,2]],np.uint16)
        codes,_,s=trace(pixels,p,np.eye(3)*2,1)
        np.testing.assert_array_equal(codes,self.core.render(pixels,p))
        self.assertEqual(s['pre_curve_above_65535_channels'],3)
        self.assertEqual(s['display_linear_above_one_channels'],3)
        self.assertEqual(s['nonpositive_luminance_pixels'],1)
        np.testing.assert_array_equal(codes[1],[0,0,0])
    def test_signed_differences_do_not_wrap(self):
        a=np.array([[[0,255,7]]],np.uint8);b=np.array([[[255,0,7]]],np.uint8)
        self.assertEqual(diff(a,b)['mean_abs_rgb8'],170)
        self.assertEqual(diff(a,b)['max_abs_rgb8'],255)
if __name__=='__main__':unittest.main()
