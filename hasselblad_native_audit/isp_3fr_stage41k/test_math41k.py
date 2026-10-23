import unittest
import numpy as np
from test_shared_render41k import curve, render, split_masks, fit_exposure, fit_shared_tone, preview_to_srgb, rgb_to_xyz_matrix


class MathTests(unittest.TestCase):
    def test_monotonic_curve_and_anchors(self):
        x=np.linspace(0,1,2001)
        for p,q in [(.1,2.5),(2.5,.1),(.4,.4),(1.3,.4),(1,1)]:
            y=curve(x,(p,q))
            self.assertTrue(np.all(np.diff(y)>0))
            np.testing.assert_allclose(curve(np.array([0,.18,1]),(p,q)),[0,.18,1],atol=1e-12)
        np.testing.assert_allclose(curve(x,(1,1)),x,atol=1e-12)

    def test_tone_preserves_linear_chromaticity_before_clipping(self):
        x=np.array([[.03,.05,.08],[.12,.10,.09]])
        _,mapped=render(x,.5,(1.3,.4))
        np.testing.assert_allclose(mapped/mapped.sum(1,keepdims=True),x/x.sum(1,keepdims=True),atol=1e-12)

    def test_separated_guarded_tile_masks(self):
        mask=np.ones((240,320),bool)
        a,b=split_masks(mask)
        self.assertFalse(np.any(a&b))
        yy,xx=np.nonzero(a|b)
        self.assertTrue(np.all((xx%40>=5)&(xx%40<35)&(yy%40>=5)&(yy%40<35)))

    def test_standard_primary_matrix_and_neutrals(self):
        m=rgb_to_xyz_matrix([(.68,.32),(.265,.69),(.15,.06)])
        np.testing.assert_allclose(m@np.ones(3),[.3127/.329,1,(1-.3127-.329)/.329],atol=1e-12)
        for i,xy in enumerate([(.68,.32),(.265,.69),(.15,.06)]):
            np.testing.assert_allclose(m[:2,i]/m[:,i].sum(),xy,atol=1e-12)
        gray=np.repeat(np.linspace(0,1,20)[:,None],3,axis=1)
        np.testing.assert_allclose(preview_to_srgb(gray,'DisplayP3'),gray,atol=1e-7)

    def test_recover_synthetic_tone_and_exposure(self):
        v=np.geomspace(.001,.45,400)
        x=np.repeat(v[:,None],3,axis=1)
        pars=(1.25,.7)
        training=[]
        for ev in [-.3,.2,.5]:
            ref,_=render(x,ev,pars);training.append((x,ref))
        found,evs,info=fit_shared_tone(training)
        self.assertTrue(info['success'])
        np.testing.assert_allclose(found,pars,atol=2e-5)
        np.testing.assert_allclose(evs,[-.3,.2,.5],atol=2e-5)
        self.assertAlmostEqual(fit_exposure(*training[1],pars),.2,places=5)


if __name__=='__main__':unittest.main()
