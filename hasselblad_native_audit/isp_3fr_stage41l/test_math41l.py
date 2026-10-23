import unittest
import numpy as np
from test_highlights41l import soft_curve,neutral_axis_gamut,render_soft,fit_tone,fit_ev
from test_shared_render41k import curve,LUMA


class HighlightTests(unittest.TestCase):
    def test_q_zero_limit_and_extended_domain(self):
        y=np.geomspace(1e-5,.99,1000)
        np.testing.assert_allclose(soft_curve(y,1.3),curve(y,(1.3,1e-8)),atol=2e-8)
        self.assertAlmostEqual(float(soft_curve(.18,1.3)),.18,places=12)
        self.assertEqual(float(soft_curve(0,1.3)),0)
        extended=soft_curve(np.geomspace(1e-5,1e6,3000),1.3)
        self.assertTrue(np.all(np.diff(extended)>0))
        self.assertTrue(np.all(extended<1))
        self.assertLess(float(soft_curve(1,1.3)),.9)
        self.assertGreater(float(soft_curve(10,1.3)),float(soft_curve(1,1.3)))

    def test_continuity_at_old_white_cutoff(self):
        y=soft_curve(np.array([1-1e-7,1,1+1e-7]),1.3)
        self.assertLess(float(np.max(np.diff(y))),1e-7)

    def test_gamut_bounds_luminance_and_identity(self):
        rng=np.random.default_rng(41)
        rgb=rng.lognormal(0,2,(2000,3))
        wanted=rng.uniform(.001,.999,2000)
        rgb*= (wanted/(rgb@LUMA))[:,None]
        out,amount=neutral_axis_gamut(rgb)
        self.assertGreaterEqual(float(out.min()),-1e-12)
        self.assertLessEqual(float(out.max()),1+1e-12)
        np.testing.assert_allclose(out@LUMA,wanted,atol=1e-12)
        inside=np.all((rgb>=0)&(rgb<=1),axis=1)
        np.testing.assert_allclose(out[inside],rgb[inside],atol=1e-12)
        self.assertTrue(np.all(amount[inside]==1))

    def test_known_smooth_curve_and_exposure_recovery(self):
        x=np.repeat(np.geomspace(.001,1.2,400)[:,None],3,axis=1)
        training=[]
        for ev in [-.5,.3,1.1]:
            ref,_,_=render_soft(x,ev,1.45);training.append((x,ref))
        p,evs,fit=fit_tone(training)
        self.assertFalse(fit['shape_at_bound'])
        self.assertAlmostEqual(p,1.45,places=5)
        np.testing.assert_allclose(evs,[-.5,.3,1.1],atol=2e-5)
        self.assertAlmostEqual(fit_ev(*training[1],1.45),.3,places=5)


if __name__=='__main__':unittest.main()
