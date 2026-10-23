"""Synthetic-only Stage35 camera neutral sensitivity tests."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from neutral_sensitivity35 import assess, stage18_camera_to_xyz_d50


def rational(x):
    return {'numerator':int(round(x*1024)), 'denominator':1024}

def fixture():
    fm=[1.,0.,0.,0.,1.,0.,0.,0.,1.]
    cc=fm.copy()
    sidecar={
        'schema':'hasselblad-photon-capture-evidence-v1',
        'calibration_evidence_usable':True,
        'original_still':{
            'selected_raw_sensor_result':{'android.sensor.neutralColorPoint':[rational(.5),rational(1),rational(.25)]},
            'selected_sensor_characteristics':{
                'android.sensor.forwardMatrix1':[rational(x) for x in fm],
                'android.sensor.forwardMatrix2':[rational(x) for x in fm],
                'android.sensor.calibrationTransform1':[rational(x) for x in cc],
                'android.sensor.calibrationTransform2':[rational(x) for x in cc],
            }
        },
        'effective_photon_export':{
            'neutral_used':[.5,1,.25],
            'forward_matrix_1':fm,
            'calibration_transform_1':cc
        }
    }
    return sidecar

class Tests(unittest.TestCase):
    def test_untouched_equal(self):
        d=assess(fixture())
        self.assertEqual(d['status'],'PASS_PRIVATE_METADATA_LINEAR_PCS_SENSITIVITY_ONLY')
        self.assertEqual(d['Stage18_matrix_relative_Frobenius_change_percent'],0.)
        self.assertEqual(d['Stage18_blue_column_delta_percent'],0.)
        self.assertFalse(d['original_selected_Camera2_vs_Photon_effective_neutral_different'])
        self.assertFalse(d['photographic_colour_error_measured'])

    def test_blue_only_different(self):
        d=fixture();d['effective_photon_export']['neutral_used'][2]=.26
        report=assess(d)
        self.assertAlmostEqual(report['Stage18_blue_column_scale_effective_over_original'],.25/.26,places=12)
        self.assertAlmostEqual(report['Stage18_other_columns_max_abs_change'],0.,places=12)
        self.assertTrue(report['original_selected_Camera2_vs_Photon_effective_neutral_different'])
        self.assertFalse(report['private_file_hash_camera_id_timestamp_calibration_values_exported'])

    def test_both_neutrals_map_to_D50(self):
        f=np.eye(3);cc=np.eye(3)
        for n in [np.asarray([.5,1.,.25]),np.asarray([.5,1.,.26]),np.asarray([.7,1.,.34])]:
            m=stage18_camera_to_xyz_d50(f,cc,n)
            np.testing.assert_allclose(m@n,np.asarray([.9642,1,.8249]),rtol=0,atol=1e-12)

    def test_mismatched_matrix_fails_closed(self):
        d=fixture();d['effective_photon_export']['calibration_transform_1'][8]=1.01
        with self.assertRaisesRegex(ValueError,'matrix_changed'):
            assess(d)

    def test_different_dual_illuminants_fail_closed(self):
        d=fixture();d['original_still']['selected_sensor_characteristics']['android.sensor.forwardMatrix2'][8]=rational(1.1)
        with self.assertRaisesRegex(ValueError,'unsupported_dual'):
            assess(d)

    def test_nonfinite_neutral_fails_closed(self):
        d=fixture();d['effective_photon_export']['neutral_used'][2]=float('nan')
        with self.assertRaisesRegex(ValueError,'invalid_neutral'):
            assess(d)

    def test_never_emits_private_capture_id(self):
        d=fixture();d['original_still']['sensor_provenance']={'original_camera_id':'private_device_7'}
        d['dng']={'sha256':'a'*64,'name':'private_location.jpg'}
        out=assess(d)
        text=repr(out)
        for forbidden in ('private_device_7','a'*64,'private_location.jpg'):
            self.assertNotIn(forbidden,text)

    def test_missing_matrices_fail_closed(self):
        d=fixture();del d['original_still']['selected_sensor_characteristics']['android.sensor.forwardMatrix1']
        with self.assertRaises(KeyError):
            assess(d)

if __name__=='__main__': unittest.main(verbosity=2)
