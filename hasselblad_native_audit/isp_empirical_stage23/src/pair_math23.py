#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage23 controlled X2DII camera RAW->in-camera JPEG chart comparison.

Owned reference arithmetic only. No Phocus TIFF or original ISP inference.
Outputs are aggregate values, never camera/source pixel or chart-patch arrays.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000

STAGE = "hasselblad-stage23-x2dii-empirical-reference-v1"
PATCH_COUNT = 24
NEUTRAL_SLOTS = (18, 19, 20, 21, 22, 23)


def require_rgb(p: np.ndarray, label: str) -> np.ndarray:
    a = np.asarray(p, dtype=np.float64)
    if a.shape != (PATCH_COUNT, 3) or not np.all(np.isfinite(a)):
        raise ValueError(label+": need exactly 24 finite RGB triples")
    if np.any(a < 0.0) or np.any(a > 1.0):
        raise ValueError(label+": outside display RGB interval")
    return a


def srgb_encode(linear: np.ndarray) -> np.ndarray:
    """Reference sRGB OETF with caller-specified display gamut restriction."""
    x = np.asarray(linear, dtype=np.float64)
    if not np.all(np.isfinite(x)) or np.any(x < 0.0):
        raise ValueError("sRGB OETF expects finite nonnegative samples")
    return np.where(x <= 0.0031308, 12.92*x, 1.055*np.power(x,1.0/2.4)-0.055)


def srgb_decode(encoded: np.ndarray) -> np.ndarray:
    x = np.asarray(encoded, dtype=np.float64)
    if not np.all(np.isfinite(x)) or np.any(x < 0.0):
        raise ValueError("sRGB EOTF expects finite nonnegative samples")
    return np.where(x <= 0.04045, x / 12.92, np.power((x+0.055)/1.055,2.4))


def delta_e00(x_encoded: np.ndarray, y_encoded: np.ndarray) -> np.ndarray:
    a, b = require_rgb(x_encoded,"candidate"),require_rgb(y_encoded,"reference")
    lab_a=rgb2lab(a.reshape(1,PATCH_COUNT,3)).reshape(PATCH_COUNT,3)
    lab_b=rgb2lab(b.reshape(1,PATCH_COUNT,3)).reshape(PATCH_COUNT,3)
    out=deltaE_ciede2000(lab_a,lab_b)
    if not np.all(np.isfinite(out)) or np.any(out < 0.0):
        raise RuntimeError("Delta E calculation invalid")
    return out


def luma(x: np.ndarray) -> np.ndarray:
    return np.asarray(x) @ np.array([0.2126,0.7152,0.0722],dtype=np.float64)


def stats(deltas: np.ndarray) -> dict:
    a=np.asarray(deltas,dtype=np.float64)
    if a.shape!=(PATCH_COUNT,) or not np.all(np.isfinite(a)) or np.any(a<0):
        raise ValueError("Invalid distances")
    return {"mean_delta_e00":round(float(np.mean(a)),5),
            "median_delta_e00":round(float(np.median(a)),5),
            "p95_delta_e00":round(float(np.quantile(a,.95)),5),
            "maximum_delta_e00":round(float(np.max(a)),5),
            "neutral_mean_delta_e00":round(float(np.mean(a[list(NEUTRAL_SLOTS)])),5),
            "chromatic_mean_delta_e00":round(float(np.mean(a[:18])),5)}


def report(raw_linear: np.ndarray, camera_jpeg_encoded: np.ndarray,
           *, file_stems_match: bool, metadata_match: bool, source_category: str,
           applied_icc_profile: bool, chart_detected_independently: bool) -> dict:
    """Compare same-frame chart patches in a declared sRGB *display* domain.

    RAW is a LibRaw-rendered linear sRGB approximation; output is not a
    camera-native RAW/XYZ colorimeter and not a Phocus-rendered result.
    """
    if not all((file_stems_match,metadata_match,chart_detected_independently)):
        raise ValueError("Pair provenance or independently detected chart absent")
    if source_category!="camera_jpeg":
        raise ValueError("Never treat Phocus TIFF or edited exports as camera JPEG")
    raw = np.asarray(raw_linear,dtype=np.float64)
    target = require_rgb(camera_jpeg_encoded,"camera_jpeg")
    if raw.shape!=(PATCH_COUNT,3) or not np.all(np.isfinite(raw)) or np.any(raw < 0):
        raise ValueError("RAW reference must be 24 nonnegative linear RGB triples")
    if luma(raw)[18] <= luma(raw)[23] or luma(srgb_decode(target))[18] <= luma(srgb_decode(target))[23]:
        raise ValueError("Chart patch orientation/neutral ramp appears invalid")
    raw_display=srgb_encode(np.clip(raw,0,1))
    raw_display=require_rgb(raw_display,"LibRaw_encoded")
    orig_de=delta_e00(raw_display,target)
    target_linear=srgb_decode(target)
    raw_y = luma(raw)[list(NEUTRAL_SLOTS)]
    jpeg_y = luma(target_linear)[list(NEUTRAL_SLOTS)]
    valid=(raw_y>1.e-4)&(jpeg_y>1.e-4)
    if not np.any(valid):raise ValueError("No usable neutral luminance for exposure comparison")
    exposure=float(np.median(jpeg_y[valid]/raw_y[valid]))
    if not math.isfinite(exposure) or exposure<0.05 or exposure>20.0:
        raise ValueError("Implausible neutral exposure scale")
    scaled_encoded=srgb_encode(np.clip(raw*exposure,0,1))
    scaled_de=delta_e00(scaled_encoded,target)
    return {
      "schema":STAGE,"status":"completed_with_comparable_chart_patches",
      "reference_source":"controlled_X2D_II_same_shutter_RAW_plus_in_camera_JPEG",
      "source_kind":"in_camera_JPEG_SDR_base_interpretation",
      "raw_decoder":"LibRaw_linear_sRGB_camera_WB_no_autobright_half_resolution",
      "output_patch_space":"display_sRGB_encoded_for_CIEDE2000",
      "patch_count":PATCH_COUNT,"neutral_patch_count":len(NEUTRAL_SLOTS),
      "pair_metadata_consistent":bool(metadata_match),
      "source_stems_match":bool(file_stems_match),
      "colorchecker_detected_separately_in_RAW_and_JPEG":bool(chart_detected_independently),
      "jpeg_icc_transformed_to_sRGB":bool(applied_icc_profile),
      "baseline_rawpy_vs_camera_JPEG":stats(orig_de),
      "exposure_only_neutral_scale":round(exposure,6),
      "exposure_scaled_rawpy_vs_camera_JPEG":stats(scaled_de),
      "gamut_and_tonality_cannot_be_disentangled_from_chart_alone":True,
      "Phocus_default_TIFF_available":False,
      "measured_illuminant_available":False,
      "independent_light_scenes":1,
      "HDR_gainmap_processed":False,
      "original_MAIN_ISP_pixel_equivalence_proven":False,
      "original_MAIN_CCM_equation_proven":False,
      "HNCS_renderer_implemented":False,
      "photographic_render_authorized":False,
      "original_vendor_tuning_exported":False,
      "original_camera_image_bytes_exported":False,
      "individual_pixel_or_patch_values_exported":False,
      "photo_render_or_Photon_source_modified":False
    }


def selftest() -> dict:
    rng=np.random.default_rng(20261022)
    # Saturated but valid synthetic chart patches; last six must form white->black ramp.
    chart=rng.uniform(0.07,0.8,(24,3))
    for i, y in enumerate([.84,.65,.48,.34,.19,.06]):chart[18+i]=y
    linear=srgb_decode(chart)
    unchanged=report(linear,chart,file_stems_match=True,metadata_match=True,
        source_category="camera_jpeg",applied_icc_profile=True,chart_detected_independently=True)
    assert unchanged["baseline_rawpy_vs_camera_JPEG"]["mean_delta_e00"]==0.0
    shifted=chart.copy();shifted[:18,0] = np.minimum(1,shifted[:18,0]+.09)
    changed=report(linear,shifted,file_stems_match=True,metadata_match=True,
        source_category="camera_jpeg",applied_icc_profile=True,chart_detected_independently=True)
    assert changed["baseline_rawpy_vs_camera_JPEG"]["mean_delta_e00"]>0.1
    negative_cases=0
    for bad in [dict(file_stems_match=False),dict(metadata_match=False),dict(source_category="phocus_tiff"),
                dict(chart_detected_independently=False)]:
        kw=dict(file_stems_match=True,metadata_match=True,source_category="camera_jpeg",
                applied_icc_profile=True,chart_detected_independently=True)
        kw.update(bad)
        try:report(linear,chart,**kw)
        except ValueError:negative_cases+=1
    assert negative_cases==4
    assert np.max(np.abs(srgb_decode(srgb_encode(linear))-linear))<1.e-12
    return {"schema":STAGE,"status":"PASS_synthetic_arithmetic_and_provenance",
            "tests":"identity_mutation_exposure_and_provenance",
            "negative_cases_passed":negative_cases,"source_input":"synthetic_only",
            "photographic_render_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--selftest",action="store_true");p.add_argument("--output",type=Path)
    a=p.parse_args()
    if not a.selftest:raise SystemExit("Only --selftest supported from this module")
    z=selftest();text=json.dumps(z,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.write_text(text)
    print(text)
