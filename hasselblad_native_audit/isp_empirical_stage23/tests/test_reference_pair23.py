#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local no-photo, no-network Stage23 provenance and colour-math tests."""
from __future__ import annotations
import json, tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from pair_math23 import (selftest,require_rgb,delta_e00,srgb_encode,srgb_decode,report)
from download_public23 import (extract_drive_id,parse_pinned_manifest,PAIR_STEM)
from run_public_pair23 import exif_provenance,extract_patches

class TestStage23(unittest.TestCase):
  def test_all_arithmetic_cases(self):
    self.assertEqual(selftest()['status'],'PASS_synthetic_arithmetic_and_provenance')

  def test_invalid_values_are_rejected(self):
    x=np.full((24,3),.5)
    for val in (-.01,1.01,np.nan):
      y=x.copy();y[10,2]=val
      with self.assertRaises(ValueError): require_rgb(y,'broken')
    with self.assertRaises(ValueError):delta_e00(x,x[:23])
    with self.assertRaises(ValueError):srgb_encode(np.array([-1.]))

  def test_expanded_color_checker_coordinates(self):
    small=np.ones((60,70,3),dtype=np.float64)*.35
    small[10:20,10:20]=.82
    quad=np.array([[10,10],[20,10],[20,20],[10,20]],dtype=float)
    measured=extract_patches(small,np.repeat(quad[None],24,axis=0))
    np.testing.assert_allclose(measured,.82,atol=1.e-12)

  def test_drive_url_trust(self):
    correct='https://drive.google.com/file/d/1BNbyF6qlJoJ6gW2FQPr3H_pV2gH9psTa/view'
    self.assertEqual(extract_drive_id(correct),'1BNbyF6qlJoJ6gW2FQPr3H_pV2gH9psTa')
    for s in ('http://drive.google.com/file/d/a/view','https://bad.example/','https://drive.google.com/uc?id=x'):
      with self.assertRaises(ValueError):extract_drive_id(s)

  def test_gdrive_pinned_manifest(self):
    # Synthetic manifest, not a recovered third-party image or licence grant.
    rawid='a'*24;jid='b'*24
    lines=['filename_raw,filename_jpeg,camera,lens,iso,wb_setting,scene_type,illuminant,download_url,notes']
    for i in range(9):
      ident=31325+i
      lines.append(f'B_{ident}.3FR,B_{ident}.JPG,X2D II 100C,XCD 90V,50,auto,chart,,https://drive.google.com/file/d/{rawid}/view,"JPEG: https://drive.google.com/file/d/{jid}/view"')
    a,b=parse_pinned_manifest(('\n'.join(lines)+'\n').encode())
    self.assertEqual((a,b),(rawid,jid))
    with self.assertRaises(ValueError):parse_pinned_manifest(('\n'.join(lines[:-1])+'\n').encode())

  def test_exif_same_shutter_and_negative_provenance(self):
    r=Path('/tmp')/(PAIR_STEM+'.3FR');j=Path('/tmp')/(PAIR_STEM+'.JPG')
    class Result:
      def __init__(self,o):self.stdout=json.dumps([o])
    def fake(cmd,*a,**k):
      info={'Model':'Hasselblad X2D II 100C','ISO':50,'DateTimeOriginal':'2026:07:19 10:33:02'}
      if cmd[-1].endswith('.JPG'):info['DateTimeOriginal']='2026:07:19 10:33:03'
      return Result(info)
    with patch('run_public_pair23.subprocess.run',side_effect=fake):
      d=exif_provenance(r,j)
    self.assertTrue(d['same_stem']);self.assertEqual(d['time_offset_seconds'],1)
    def wrong(cmd,*a,**k):
      info={'Model':'Hasselblad X2D II 100C','ISO':50,'DateTimeOriginal':'2026:07:19 10:33:02'}
      if cmd[-1].endswith('.JPG'):info['DateTimeOriginal']='2026:07:19 10:33:05'
      return Result(info)
    with patch('run_public_pair23.subprocess.run',side_effect=wrong):
      with self.assertRaises(ValueError):exif_provenance(r,j)
    with self.assertRaises(ValueError):exif_provenance(r,Path('/tmp/DIFFERENT.JPG'))

if __name__=='__main__':unittest.main(verbosity=2)
