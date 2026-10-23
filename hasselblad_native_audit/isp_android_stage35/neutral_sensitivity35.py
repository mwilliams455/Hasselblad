#!/usr/bin/env python3
"""Offline Stage35 sensitivity probe: compares source and effective neutrals.

Implements the validated Stage18 DNG neutral/reference-matrix algebra, using
sidecar metadata that remains PRIVATE. Emits only scalar sensitivity and scope
flags. This does not read a DNG pixel, render an image, calibrate the sensor,
change an APK, or reconstruct Hasselblad MAIN CCM/HNCS colour science.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np

D50 = np.asarray([.9642, 1., .8249], dtype=np.float64)


def _rational_matrix(obj: dict, name: str) -> np.ndarray:
    entries = obj[name]
    if len(entries) != 9:
        raise ValueError('bad_matrix_count')
    vals = np.asarray([x['numerator']/x['denominator'] for x in entries], dtype=np.float64)
    if not np.isfinite(vals).all():
        raise ValueError('matrix_nonfinite')
    return vals.reshape((3,3))


def _neutral(obj: dict, name: str, rational: bool) -> np.ndarray:
    entries = obj[name]
    if len(entries) != 3:
        raise ValueError('neutral_length')
    vals = np.asarray([(x['numerator']/x['denominator']) if rational else x
                      for x in entries], dtype=np.float64)
    if not np.isfinite(vals).all() or (vals <= 0).any():
        raise ValueError('invalid_neutral')
    return vals


def stage18_camera_to_xyz_d50(fm: np.ndarray, cc: np.ndarray,
                               neutral: np.ndarray, analog_balance=None) -> np.ndarray:
    """Same matrix order as Stage18's hb_dng_pcs_build (single-profile case)."""
    fm = np.asarray(fm, dtype=np.float64).reshape((3,3))
    cc = np.asarray(cc, dtype=np.float64).reshape((3,3))
    neutral = np.asarray(neutral, dtype=np.float64)
    ab = np.eye(3, dtype=np.float64) if analog_balance is None else np.diag(analog_balance)
    if not all(np.isfinite(x).all() for x in (fm,cc,neutral,ab)):
        raise ValueError('nonfinite')
    totals = fm.sum(axis=1)
    if (np.abs(totals) < 1e-12).any():
        raise ValueError('singular_forward')
    fmnorm = fm*(D50/totals)[:,None]
    inv_abcc = np.linalg.inv(ab@cc)
    wn = neutral / neutral.max()
    refwhite = inv_abcc@wn
    if (refwhite <= 0).any():
        raise ValueError('invalid_reference_white')
    camera_to_pcs = fmnorm@np.diag(1/refwhite)@inv_abcc
    if not np.allclose(camera_to_pcs@wn,D50,rtol=0,atol=1e-10):
        raise ValueError('PCS_white_not_preserved')
    return camera_to_pcs


def assess(sidecar: dict) -> dict:
    if sidecar.get('schema') != 'hasselblad-photon-capture-evidence-v1':
        raise ValueError('unexpected_capture_schema')
    if sidecar.get('calibration_evidence_usable') is not True:
        raise ValueError('calibration_not_usable')
    original = sidecar['original_still']
    characteristics = original['selected_sensor_characteristics']
    captured = original['selected_raw_sensor_result']
    effective = sidecar['effective_photon_export']
    original_n = _neutral(captured, 'android.sensor.neutralColorPoint', True)
    effective_n = _neutral(effective, 'neutral_used', False)
    fm = _rational_matrix(characteristics, 'android.sensor.forwardMatrix1')
    cc = _rational_matrix(characteristics, 'android.sensor.calibrationTransform1')
    effective_fm = np.asarray(effective['forward_matrix_1'], dtype=np.float64).reshape(3,3)
    effective_cc = np.asarray(effective['calibration_transform_1'], dtype=np.float64).reshape(3,3)
    # Stage34 measured these as identical, and this probe must independently
    # confirm that in original records before isolating a neutral-only effect.
    if not (np.allclose(fm,effective_fm,rtol=0,atol=5e-4) and
            np.allclose(cc,effective_cc,rtol=0,atol=5e-4)):
        raise ValueError('matrix_changed_beyond_Stage34_tolerance')
    if not (np.array_equal(_rational_matrix(characteristics,'android.sensor.forwardMatrix2'),fm)
            and np.array_equal(_rational_matrix(characteristics,'android.sensor.calibrationTransform2'),cc)):
        raise ValueError('unsupported_dual_illuminant_matrix')
    M0 = stage18_camera_to_xyz_d50(fm,cc,original_n)
    M1 = stage18_camera_to_xyz_d50(fm,cc,effective_n)
    d = M1-M0
    bc=np.linalg.norm(M0[:,2])
    blue_ratio = float(M0[:,2]@M1[:,2]/(M0[:,2]@M0[:,2]))
    residual=float(np.linalg.norm(M1[:,2]-blue_ratio*M0[:,2])/bc)
    return {
        'schema':'hasselblad-stage35-neutral-sensitivity-v1',
        'status':'PASS_PRIVATE_METADATA_LINEAR_PCS_SENSITIVITY_ONLY',
        'input_is_original_capture_sidecar':True,
        'DNG_AsShotNeutral_source_from_Stage34':'MATCHES_PHOTON_EFFECTIVE_ONLY',
        'original_selected_Camera2_vs_Photon_effective_neutral_different':bool(not np.array_equal(original_n,effective_n)),
        'DNG_sdk_exact_interpolation_verified':False,
        'assumes_unchanged_single_profile_CameraCalibration_and_ForwardMatrix':True,
        'Stage24_identity_AnalogBalance_assumed':True,
        'Stage18_blue_column_scale_effective_over_original':blue_ratio,
        'Stage18_blue_column_delta_percent':(blue_ratio-1)*100,
        'Stage18_other_columns_max_abs_change':float(np.abs(d[:,:2]).max()),
        'Stage18_blue_column_scale_fit_relative_residual':residual,
        'Stage18_all_matrix_entries_max_abs_change':float(np.abs(d).max()),
        'Stage18_matrix_relative_Frobenius_change_percent':float(np.linalg.norm(d)/np.linalg.norm(M0)*100),
        'source_DNG_pixels_loaded':False,
        'fullframe_Raw_colour_test_performed':False,
        'photographic_colour_error_measured':False,
        'original_Hasselblad_Eagle2_CCM_equation_proven':False,
        'private_file_hash_camera_id_timestamp_calibration_values_exported':False,
        'existing_phone_DNG_and_JPEG_modified':False,
        'next_step':'Keep original Camera2 neutral separately from Photon effective neutral for opt-in diagnostics; validate input photos without changing saved output',
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--capture-sidecar',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    if a.capture_sidecar.stat().st_size>4*1024*1024:
        raise ValueError('input_excessive')
    result=assess(json.loads(a.capture_sidecar.read_text()))
    rendered=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.output:
        a.output.write_text(rendered)
    print(rendered,end='')
if __name__=='__main__':main()
