#!/usr/bin/env python3
"""Synthetic DNGs for profile selection and scene-linear metadata contracts."""
import argparse
import json
import struct
import sys
from pathlib import Path
import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'isp_android_stage32/tests'), str(ROOT/'isp_colour_stage24/src')]
from make_stage32_dng_fixtures import mktags
import offline_render24 as old

D50 = np.array([.9642, 1, .8249])
FM = np.array([[.7, .2, .0642], [.2, .7, .1], [.05, .2, .5749]])
CC = np.array([[1, .12, 0], [0, 1, .08], [.04, 0, 1]])
AB = np.array([1.1, .9, 1.2])
NEUTRAL = np.array([.5, 1, .25])


def reference(cc, neutral):
    inverse = np.linalg.inv(np.diag(AB) @ cc)
    white = inverse @ (neutral/neutral.max())
    normalized = np.diag(D50/FM.sum(1)) @ FM
    return normalized @ np.diag(1/white) @ inverse


def rational(values, signed=True):
    a = np.asarray(values).ravel()
    pairs = np.c_[np.rint(a*10000).astype(int), np.full(len(a),10000)].ravel()
    return (10 if signed else 5, len(a), struct.pack('<'+str(len(pairs))+('i' if signed else 'I'), *pairs))


def write(path, tags):
    def layout():
        base = 8+2+len(tags)*12+4
        entries, data = [], bytearray()
        for tag,(kind,count,value) in sorted(tags.items()):
            if len(value)<=4: field=value.ljust(4,b'\0')
            else:
                while (base+len(data))%4:data.append(0)
                field=struct.pack('<I',base+len(data));data.extend(value)
            entries.append(struct.pack('<HHI',tag,kind,count)+field)
        return b'II'+struct.pack('<HIH',42,8,len(tags))+b''.join(entries)+bytes(4)+data
    header=layout();tags[273]=(4,1,struct.pack('<I',len(header)));header=layout()
    raw=np.full((64,64),400,dtype='<u2');raw[::2,::2]=220;raw[1::2,1::2]=150
    path.write_bytes(header+raw.tobytes())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    cases = [
        ('identity',None,None,False,True), ('absent',None,None,True,True),
        ('matching',b'fixture\0',b'fixture\0',True,True),
        ('matching_byte',b'fixture\0',b'fixture\0',True,True),
        ('mismatch',b'camera\0',b'profile\0',True,False),
        ('only_camera',b'camera\0',None,True,False),
        ('only_profile',None,b'profile\0',True,False),
        ('empty',b'\0',b'\0',True,True),
        ('mismatch_dual',b'camera\0',b'profile\0',True,False),
        ('scaled_neutral',None,None,True,True),
        ('short_neutral',None,None,True,True),
        ('output_reference1',None,None,False,True),
        ('output_reference2',None,None,False,True),
        ('unterminated',b'broken',b'broken',True,True),
    ]
    manifest=[];python_checks=0
    lib=old.compile_shared(a.out/'pcs48.so')
    for name,cs,ps,has_cc,matches in cases:
        tags=mktags(gains=False,big_endian=False)
        tags[50713]=(3,2,struct.pack('<2H',2,2));tags[50714]=(3,4,struct.pack('<4H',64,64,64,64))
        tags[50964]=rational(FM);tags[50965]=rational(FM)
        tags[50727]=rational(AB,False)
        neutral=NEUTRAL*2.7 if name=='scaled_neutral' else NEUTRAL
        tags[50728]=rational(neutral,False)
        if name=='short_neutral':tags[50728]=(3,3,struct.pack('<3H',2,4,1))
        if has_cc:
            tags[50723]=rational(CC);tags[50724]=rational(CC)
        else:
            tags.pop(50723,None);tags.pop(50724,None)
        if name=='mismatch_dual':tags[50724]=rational(CC+np.eye(3)*.2)
        for tag,value in ((50931,cs),(50932,ps)):
            if value is not None:tags[tag]=(1 if name in ('matching_byte','unterminated') else 2,len(value),value)
        error=''
        if name.startswith('output_reference'):
            tags[50879]=(3,1,struct.pack('<H',int(name[-1])));error='output_referred_DNG_not_supported'
        if name=='unterminated':error='calibration_signature_not_terminated'
        path=a.out/(name+'.dng');write(path,tags)
        expected=reference(CC if has_cc and matches else np.eye(3),NEUTRAL)
        (a.out/(name+'.matrix')).write_bytes(expected.astype('<f8').tobytes())
        manifest.append('\t'.join([name,error or 'OK',str(int(has_cc and matches))]))
        try:
            with tifffile.TiffFile(path) as t:m=old.extract_metadata(t.pages[0].tags)
            actual=np.asarray(old.context(lib,m,0).camera_to_xyz_d50).reshape(3,3)
            assert not error, name+' should be rejected'
            assert np.allclose(actual,expected,rtol=0,atol=1e-12), name
            assert (m['cc1'] is not None)==(has_cc and matches), name
        except ValueError:
            assert error,name+' unexpectedly rejected'
        python_checks+=1
    (a.out/'manifest.tsv').write_text('\n'.join(manifest)+'\n')
    receipt={'schema':'hasselblad-stage48-python-metadata-v1','status':'PASS','cases':python_checks,
             'synthetic_only':True,'independent_DNG_matrix_reference':True,
             'scaled_and_SHORT_neutral_supported':True}
    (a.out/'PYTHON_METADATA48.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
