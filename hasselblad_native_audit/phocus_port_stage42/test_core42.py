#!/usr/bin/env python3
"""Synthetic analytical cases, including bad-input transactional guarantees."""
import ctypes as C, tempfile, unittest
from pathlib import Path
import numpy as np
from core42 import Core

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.core=Core(Path(cls.tmp.name)/'core.so')
    def params(self):
        # Y=green; Cb=R-G; Cr=B-G. An identity chroma grid reconstructs RGB.
        yy,xx=np.mgrid[:89,:105]
        grid=np.stack([xx-20,yy-32],axis=-1).astype(float)
        return self.core.params([[0,1,0],[1,-1,0],[0,-1,1]],
            [[999,1,0],[-999,0,0],[123,0,1]],grid,False,
            np.arange(65536,dtype=np.float32),[2,0,0,1])
    def test_neutral_dark_and_luminance_column_ignored(self):
        p=self.params();x=np.repeat(np.array([0,1,2,255,15500,65535])[:,None],3,1)
        np.testing.assert_array_equal(self.core.render(x,p),x)
    def test_exact_interior_and_curve_truncation(self):
        p=self.params();x=np.array([[1200,1000,1500],[500,1000,1000]],dtype=np.uint16)
        np.testing.assert_array_equal(self.core.render(x,p),x)
        p._arrays[1][:]=np.minimum(np.arange(65536)+.75,65535)
        np.testing.assert_array_equal(self.core.render(x,p),x)
    def test_clamped_grid_edges(self):
        p=self.params();x=np.array([[65535,32,0],[0,32,65535]],dtype=np.uint16)
        np.testing.assert_array_equal(self.core.render(x,p),[[116,32,0],[12,32,88]])
    def test_negative_luminance_bypasses_curve(self):
        p=self.params();p.first[1]=-1;p._arrays[1][:]=900
        np.testing.assert_array_equal(self.core.render([[100,100,100]],p),[[0,0,0]])
    def test_gain_ownership_and_exposure(self):
        p=self.params();p.wb_owner=0;p.wb[:]=[2,1,1];p.exposure=2
        np.testing.assert_array_equal(self.core.render([[500,500,500]],p),[[2000,1000,1000]])
        for owner in (1,2):
            p.wb_owner=owner
            with self.assertRaises(ValueError):self.core.render([[500,500,500]],p)
    def test_clipping(self):
        p=self.params();p.exposure=2
        np.testing.assert_array_equal(self.core.render([[65535]*3],p),[[65535]*3])
    def test_invalid_preserves_output(self):
        for field,val in [('exposure',float('nan')),('width',257),('curve_count',1),('wb_owner',3)]:
            p=self.params();setattr(p,field,val)
            src=np.array([[1,2,3]],dtype=np.uint16);dst=np.array([[777]*3],dtype=np.uint16)
            self.assertEqual(self.core.lib.hb42_render(C.byref(p),src.ctypes.data,1,dst.ctypes.data),1)
            np.testing.assert_array_equal(dst,777)
        for name,index in [('curve',16),('grid',16)]:
            p=self.params();p._arrays[1 if name=='curve' else 0].ravel()[index]=float('nan')
            self.assertEqual(self.core.lib.hb42_validate(C.byref(p)),1)
    def test_alias_rejected(self):
        p=self.params();src=np.array([[1,2,3]],dtype=np.uint16)
        self.assertEqual(self.core.lib.hb42_render(C.byref(p),src.ctypes.data,1,src.ctypes.data),2)
        np.testing.assert_array_equal(src,[[1,2,3]])
if __name__=='__main__':unittest.main()
