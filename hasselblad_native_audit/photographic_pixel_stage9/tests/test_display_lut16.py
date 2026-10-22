#!/usr/bin/env python3
"""Stage9 original-native X2D II DISPLAY, not photographic MAIN, test vectors.

The 20 input/output pairs are public-safe SYNTHETIC recorded outputs of the
original libduml_hal.so functions from pixel_contract_20261019 on 2026-10-19.
All words are locally generated (no firmware, vendor LUT or photo needed).
"""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'src'/'hb_display_lut16.c'
# Prior native execution: 20 synthetic trilinear inputs -> original outputs.
ORIGINAL_NATIVE = [
 ([0,0,0],[0.012942612942612943,0.07594627594627594,0.22246642246642245]),
 ([1,1,1],[0.6832722832722833,0.002442002442002442,0.3833943833943834]),
 ([1,0,0],[0.47814407814407817,0.2993894993894994,0.9367521367521368]),
 ([0,1,0],[0.14847374847374847,0.37997557997557996,0.28473748473748473]),
 ([0,0,1],[0.08253968253968254,0.4752136752136752,0.607081807081807]),
 ([1,1,0],[0.6136752136752137,0.6034188034188034,0.999023199023199]),
 ([1,0,1],[0.5477411477411478,0.6986568986568986,0.32112332112332115]),
 ([0,1,1],[0.21807081807081807,0.7792429792429793,0.6693528693528693]),
 ([1/15,7/15,14/15],[0.17216117216117216,0.6053724053724053,0.5897435897435898]),
 ([14/15,2/15,1/15],[0.46984126984126984,0.3516483516483517,0.8547008547008547]),
 ([0.123,0.456,0.789],[0.18687667887667886,0.557089133089133,0.5017509157509158]),
 ([0.876,0.234,0.567],[0.49163492063492065,0.5692100122100121,0.9096227106227107]),
 ([0.5,0.5,0.5],[0.34810744810744815,0.5393162393162393,0.5295482295482296]),
 ([0.999999999,0.999999997,0.999999991],[0.6832722817741149,0.002442192760673392,0.38339437513431024]),
 ([1e-9,3e-9,9e-9],[0.012942614440781442,0.07594628067521367,0.22246642293162394]),
 ([0.067,0.134,0.201],[0.07626129426129426,0.21190964590964592,0.2495970695970696]),
 ([0.934,0.867,0.799],[0.6205543345543347,0.8672503052503054,0.14491819291819313]),
 ([1,0.345,0.678],[0.5720891330891331,0.6749829059829059,0.135034188034188]),
 ([0.123,1,0.789],[0.26060561660561665,0.7224810744810745,0.5356263736263737]),
 ([0.123,0.456,1],[0.20156166056166058,0.6413345543345543,0.6466996336996338]),
]

def component(c,r,g,b):
    if c==0:return (127*r+37*g+19*b+53)&4095
    if c==1:return (61*r+83*g+109*b+311)&4095
    return (13*r*r+17*g+7*b*b+911)&4095

def synthetic_table():
    words=(ct.c_uint32*6144)(*([0xa0005000]*6144))
    for r in range(16):
        for g in range(16):
            for b in range(16):
                q=128*r+8*g+b//2
                sh=16*(b&1)
                for ch in range(3):words[q+2048*ch] |= component(ch,r,g,b)<<sh
    return words

def run():
    with tempfile.TemporaryDirectory(prefix='hb-stage9-') as d:
        so=Path(d)/'display.so'
        subprocess.run(['cc','-std=c11','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror','-fPIC','-shared',str(SRC),'-lm','-o',str(so)],check=True)
        lib=ct.CDLL(str(so))
        words=ct.POINTER(ct.c_uint32)
        rgb=ct.POINTER(ct.c_double)
        lib.hb_display_lut16_node.argtypes=[words,ct.c_size_t,ct.c_uint32,ct.c_uint32,ct.c_uint32,rgb]
        lib.hb_display_lut16_node.restype=ct.c_int
        lib.hb_display_lut16_trilinear.argtypes=[words,ct.c_size_t,rgb,rgb]
        lib.hb_display_lut16_trilinear.restype=ct.c_int
        table=synthetic_table()
        before=bytes(table)
        max_node_error=0.0
        for r in range(16):
            for g in range(16):
                for b in range(16):
                    out=(ct.c_double*3)(-5,-5,-5)
                    assert lib.hb_display_lut16_node(table,6144,r,g,b,out)==0
                    for ch in range(3):
                        error=abs(out[ch]-component(ch,r,g,b)/4095.0)
                        max_node_error=max(max_node_error,error)
                        assert error<1e-15,(r,g,b,ch,error)
        max_native_error=0.0
        for (xyz,reference) in ORIGINAL_NATIVE:
            inp=(ct.c_double*3)(*xyz)
            out=(ct.c_double*3)(-5,-5,-5)
            assert lib.hb_display_lut16_trilinear(table,6144,inp,out)==0
            max_native_error=max(max_native_error,max(abs(out[j]-reference[j]) for j in range(3)))
            # The supplied input is valid with simultaneous input/output pointer.
            in_place=(ct.c_double*3)(*xyz)
            assert lib.hb_display_lut16_trilinear(table,6144,in_place,in_place)==0
            assert max(abs(in_place[j]-out[j]) for j in range(3))<1e-15
        assert max_native_error<=1e-12,max_native_error
        assert bytes(table)==before
        negative=0
        for (r,g,b,want) in [(16,0,0,3),(0,16,0,3),(0,0,16,3),(0,0,0,2)]:
            out=(ct.c_double*3)(-7,-7,-7)
            status=lib.hb_display_lut16_node(table,6143 if r==g==b==0 else 6144,r,g,b,out)
            assert status==want and list(out)==[-7,-7,-7]
            negative+=1
        for values in [(-0.001,0,0),(0,1.0001,0),(0,0,float('nan')),(0,float('inf'),0)]:
            inp=(ct.c_double*3)(*values)
            out=(ct.c_double*3)(-7,-7,-7)
            assert lib.hb_display_lut16_trilinear(table,6144,inp,out)==3
            assert list(out)==[-7,-7,-7]
            negative+=1
        out=(ct.c_double*3)(-7,-7,-7)
        inp=(ct.c_double*3)(.5,.4,.3)
        assert lib.hb_display_lut16_trilinear(table,6143,inp,out)==2
        assert list(out)==[-7,-7,-7]
        negative+=1
        # An output pointer into the const table must be refused without writes.
        ptr=ct.cast(table,ct.POINTER(ct.c_double))
        assert lib.hb_display_lut16_node(table,6144,0,0,0,ptr)==4
        assert bytes(table)==before
        negative+=1
        report={
            'schema':'hasselblad-stage9-display-format-native-parity-v1',
            'status':'PASS',
            'original_vendor_reference':'X2D II libduml_hal.so, saved native output fixture, 2026-10-19',
            'reference_scope':'DISPLAY-HAL only, NOT photographic MAIN_3DLUT',
            'vendor_library_reexecuted_in_this_run':False,
            'original_synthetic_trilinear_vectors':len(ORIGINAL_NATIVE),
            'max_absolute_native_vector_error':max_native_error,
            'node_coordinates_verified':4096,
            'node_channel_values_verified':12288,
            'max_absolute_node_error':max_node_error,
            'negative_nonmutating_cases':negative,
            'original_data_mutated':False,
            'not_a_photographic_renderer':True,
            'camera_main_lut_format_verified':False,
            'phone_colour_changed':False,
            'camera_profile_payload_used':False
        }
        return report

if __name__=='__main__':
    r=run();print(json.dumps(r,indent=2))
