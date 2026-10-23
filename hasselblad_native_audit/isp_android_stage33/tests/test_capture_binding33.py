#!/usr/bin/env python3
"""Synthetic-only host tests; never load private photos or camera sidecars."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_capture_binding33 import proof


def fixtures():
    stage32 = {
        "schema": "hasselblad-stage32-real-dng-centre-tile-v1",
        "status": "PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY",
        "input_is_synthetic": False,
        "native_stage24_status_code": 0,
        "native_stage24_PCS_only": True,
        "physical_sensor_binding_proven": False,
        "photographic_colour_still_photon": True,
        "saved_photo_or_original_dng_modified": False,
        "source_dng_sha256": "a" * 64,
        "source_dng_bytes": 25171227,
        "raw_dimensions": [4096, 3072],
        "CFA": "RGGB"
    }
    capture = {
        "schema": "hasselblad-photon-capture-evidence-v1",
        "input_frame_count": 1,
        "calibration_evidence_usable": True,
        "pairing_status": "image_timestamp_equals_selected_still_result_timestamp",
        "frame_number": "98",
        "dng": {
            "sha256": "a" * 64,
            "bytes": 25171227,
            "name": "PRIVATE_NOT_EXPORTABLE.dng"
        },
        "original_still": {
            "selected_result_frame_number": "98",
            "selected_sensor_timestamp_ns": "227922340825514",
            "selected_raw_sensor_result": {
                "android.sensor.timestamp": "227922340825514",
            },
            "sensor_provenance": {
                "sensor_provenance_matched": True,
                "result_camera_id_matched": True,
                "request_targets_recorded_raw_surface": True,
                "selected_and_logical_frame_number_matched": True,
                "selected_characteristics_are_logical": False,
                "selected_calibration_camera_id": "private_physical_camera_A",
                "selected_result_camera_id": "private_physical_camera_A",
            },
            "selected_sensor_characteristics": {
                "android.sensor.info.colorFilterArrangement": 0
            },
        },
        "delivered_raw": {
            "sensor_timestamp_ns": "227922340825514",
            "format": 32,
            "delivered_width": 4096,
            "delivered_height": 3072,
            "copied_width": 4096,
            "copied_height": 3072,
            "copied_crop_x": 0,
            "copied_crop_y": 0,
            "copy_offset_bytes": 0,
            "binned": False,
            "pixel_stride_bytes": 2
        }
    }
    return stage32, capture


class Stage33(unittest.TestCase):
    def test_positive_case_reports_only_non_private_fields(self):
        a, b = fixtures()
        response = proof(a, b)
        self.assertEqual(response["status"], "PASS_RECORDED_DNG_PHYSICAL_FRAME_BINDING")
        self.assertTrue(response["matching_dng_hash_verified"])
        self.assertTrue(response["recorded_capture_physical_sensor_binding_proven"])
        self.assertFalse(response["independent_hardware_attestation_proven"])
        string = json.dumps(response)
        self.assertNotIn("a" * 64, string)
        self.assertNotIn("227922340825514", string)
        self.assertNotIn("PRIVATE_NOT_EXPORTABLE", string)
        self.assertNotIn("private_physical_camera_A", string)

    def test_one_mutation_at_a_time_must_fail_closed(self):
        cases = [
            ("wrong source hash", ("b", "dng", "sha256"), "b" * 64),
            ("wrong source bytes", ("b", "dng", "bytes"), 25171226),
            ("changed source report", ("a", "source_dng_sha256"), "b" * 64),
            ("wrong frame", ("b", "original_still", "selected_result_frame_number"), "99"),
            ("wrong camera", ("b", "original_still", "sensor_provenance",
                               "selected_result_camera_id"), "different_id"),
            ("physical not checked", ("b", "original_still", "sensor_provenance",
                                     "sensor_provenance_matched"), False),
            ("logical camera", ("b", "original_still", "sensor_provenance",
                                "selected_characteristics_are_logical"), True),
            ("bad metadata", ("b", "calibration_evidence_usable"), False),
            ("wrong pairing", ("b", "pairing_status"), "image_timestamp_differs_from_selected_still_result_timestamp"),
            ("timestamp result", ("b", "original_still", "selected_raw_sensor_result",
                                  "android.sensor.timestamp"), "227922340825513"),
            ("raw timestamp", ("b", "delivered_raw", "sensor_timestamp_ns"), "227922340825513"),
            ("wrong image width", ("b", "delivered_raw", "copied_width"), 4000),
            ("raw copied from crop", ("b", "delivered_raw", "copy_offset_bytes"), 2),
            ("raw binned", ("b", "delivered_raw", "binned"), True),
            ("wrong physical CFA", ("b", "original_still", "selected_sensor_characteristics",
                                    "android.sensor.info.colorFilterArrangement"), 2),
            ("stage32 not real", ("a", "input_is_synthetic"), True),
            ("stage32 native failed", ("a", "native_stage24_status_code"), 3),
            ("stage32 non PCS", ("a", "native_stage24_PCS_only"), False),
            ("stage32 unverified binding true", ("a", "physical_sensor_binding_proven"), True),
            ("different sidecar schema", ("b", "schema"), "stage33_wrong"),
            ("source photo changed", ("a", "saved_photo_or_original_dng_modified"), True),
            ("different DNG dimensions", ("a", "raw_dimensions"), [3072, 4096]),
            ("capture count more than 1", ("b", "input_frame_count"), 3),
            ("bad pixel stride", ("b", "delivered_raw", "pixel_stride_bytes"), 1),
            ("bad RAW source format", ("b", "delivered_raw", "format"), 35),
        ]
        for title, path, value in cases:
            with self.subTest(title=title):
                a, b = fixtures()
                target = a if path[0] == "a" else b
                for key in path[1:-1]:
                    target = target[key]
                target[path[-1]] = value
                result = proof(a, b)
                self.assertEqual(result["status"], "NOT_PROVEN")
                self.assertFalse(result["matching_dng_hash_verified"])
                self.assertFalse(result["recorded_capture_physical_sensor_binding_proven"])
                self.assertNotIn("private_physical_camera_A", json.dumps(result))
                self.assertNotIn("227922340825514", json.dumps(result))
                self.assertNotIn("a" * 64, json.dumps(result))
        self.assertEqual(len(cases), 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
