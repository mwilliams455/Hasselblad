#!/usr/bin/env python3
"""Stage33: bind a Stage32 *real* DNG report to its matching Photon .capture.json.

An offline, fail-closed check of recorded metadata, NOT a camera attestation,
HNCS renderer, pixel oracle or ISP change. The source images are never opened
or modified; only a redacted status report is emitted.

Do not commit real reports or camera IDs. Pass private files in a private directory.
"""
from __future__ import annotations

import argparse
import hmac
import json
from pathlib import Path
import re

MAX_JSON_BYTES = 4 * 1024 * 1024
STAGE32_SCHEMA = "hasselblad-stage32-real-dng-centre-tile-v1"
CAPTURE_SCHEMA = "hasselblad-photon-capture-evidence-v1"
VALID_HASH = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = re.compile(r"[0-9]{1,20}\Z")


def report_fail(reason: str) -> dict:
    return {
        "schema": "hasselblad-stage33-dng-capture-identity-v1",
        "status": "NOT_PROVEN",
        "reason": reason,
        "matching_dng_hash_verified": False,
        "recorded_capture_physical_sensor_binding_proven": False,
        "recorded_capture_timestamp_and_frame_binding_proven": False,
        "independent_hardware_attestation_proven": False,
        "private_hash_camera_id_timestamp_or_pixels_exported": False,
        "original_hasselblad_MAIN_pixel_equivalence_proven": False,
        "saved_photo_renderer_still_photon": True,
    }


def require(cond: bool, reason: str) -> None:
    if not cond:
        raise Rejection(reason)


class Rejection(ValueError):
    """All messages are fixed reason tokens, never private input strings."""


def get_obj(parent: dict, key: str, reason: str) -> dict:
    value = parent.get(key)
    require(isinstance(value, dict), reason)
    return value


def get_decimal(parent: dict, key: str, reason: str) -> str:
    value = parent.get(key)
    # JSON booleans are int subclasses; reject. Original CaptureEvidence stores
    # camera2 long values as decimal strings to avoid JS double precision loss.
    require(isinstance(value, str) and DECIMAL.fullmatch(value) is not None, reason)
    return value


def get_integer(parent: dict, key: str, reason: str) -> int:
    value = parent.get(key)
    require(type(value) is int and value >= 0, reason)
    return value


def proof(stage32: dict, capture: dict) -> dict:
    """A matching receipt is *recorded provenance*, not cryptographic attestation.

    The CaptureEvidence snapshot must have recorded original RAW ownership before
    Photon substitutions, and the DNG hash must match the file that Stage32
    independently read from the document picker. No source values are copied
    into the proof.
    """
    try:
        require(stage32.get("schema") == STAGE32_SCHEMA, "wrong_stage32_schema")
        require(stage32.get("status") == "PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY",
                "real_dng_native_test_not_passed")
        require(stage32.get("input_is_synthetic") is False, "synthetic_dng_unacceptable")
        require(stage32.get("native_stage24_status_code") == 0,
                "native_colour_diagnostic_not_passed")
        require(stage32.get("physical_sensor_binding_proven") is False,
                "stage32_claims_unverified_physical_binding")
        require(stage32.get("saved_photo_or_original_dng_modified") is False,
                "stage32_source_mutation_reported")
        require(stage32.get("photographic_colour_still_photon") is True,
                "unexpected_phone_renderer_claim")
        h = stage32.get("source_dng_sha256")
        require(isinstance(h, str) and VALID_HASH.fullmatch(h) is not None,
                "stage32_dng_hash_invalid")
        size = get_integer(stage32, "source_dng_bytes", "stage32_dng_size_invalid")
        require(0 < size <= 256 * 1024 * 1024, "stage32_dng_size_invalid")
        shape = stage32.get("raw_dimensions")
        require(isinstance(shape, list) and len(shape) == 2
                and all(type(x) is int and 0 < x <= 16384 for x in shape),
                "stage32_raw_geometry_invalid")
        require(stage32.get("CFA") == "RGGB", "stage32_cfa_not_RB")
        require(stage32.get("native_stage24_PCS_only") is True,
                "stage32_processing_scope_invalid")
        require(capture.get("schema") == CAPTURE_SCHEMA, "wrong_capture_sidecar_schema")

        dng = get_obj(capture, "dng", "capture_dng_record_missing")
        recorded_hash = dng.get("sha256")
        require(isinstance(recorded_hash, str)
                and VALID_HASH.fullmatch(recorded_hash) is not None,
                "capture_dng_hash_invalid")
        require(hmac.compare_digest(h, recorded_hash), "dng_hash_mismatch")
        require(get_integer(dng, "bytes", "capture_dng_size_invalid") == size,
                "dng_file_size_mismatch")

        require(capture.get("calibration_evidence_usable") is True,
                "capture_evidence_not_calibration_usable")
        require(capture.get("pairing_status")
                == "image_timestamp_equals_selected_still_result_timestamp",
                "original_raw_frame_timestamp_not_matched")
        require(get_integer(capture, "input_frame_count", "raw_burst_count_unproven") == 1,
                "raw_burst_count_unproven")
        original = get_obj(capture, "original_still", "original_still_missing")
        provenance = get_obj(original, "sensor_provenance", "physical_sensor_provenance_missing")
        for key in ("sensor_provenance_matched", "result_camera_id_matched",
                    "request_targets_recorded_raw_surface",
                    "selected_and_logical_frame_number_matched"):
            require(provenance.get(key) is True, "sensor_provenance_" + key + "_not_proven")
        require(provenance.get("selected_characteristics_are_logical") is False,
                "selected_camera_is_logical_not_proven_physical")
        camera = provenance.get("selected_calibration_camera_id")
        result_id = provenance.get("selected_result_camera_id")
        require(isinstance(camera, str) and bool(camera)
                and isinstance(result_id, str) and camera == result_id,
                "physical_camera_id_does_not_match_result")

        frame = get_decimal(capture, "frame_number", "capture_frame_number_missing")
        require(frame == get_decimal(original, "selected_result_frame_number",
                                     "selected_frame_number_mismatch"),
                "selected_frame_number_mismatch")
        stamp = get_decimal(original, "selected_sensor_timestamp_ns",
                            "selected_capture_sensor_timestamp_missing")
        result = get_obj(original, "selected_raw_sensor_result", "sensor_result_missing")
        require(stamp == get_decimal(result, "android.sensor.timestamp",
                                     "result_sensor_timestamp_mismatch"),
                "result_sensor_timestamp_mismatch")
        raw = get_obj(capture, "delivered_raw", "delivered_raw_geometry_missing")
        require(stamp == get_decimal(raw, "sensor_timestamp_ns",
                                     "raw_sensor_timestamp_mismatch"),
                "raw_sensor_timestamp_mismatch")
        require(get_integer(raw, "delivered_width", "delivered_width_missing") == shape[0]
                and get_integer(raw, "delivered_height", "delivered_height_missing") == shape[1]
                and get_integer(raw, "copied_width", "copied_width_missing") == shape[0]
                and get_integer(raw, "copied_height", "copied_height_missing") == shape[1],
                "raw_geometry_not_bound_to_dng")
        require(get_integer(raw, "copy_offset_bytes", "copy_offset_missing") == 0,
                "nonzero_raw_copy_offset")
        require(raw.get("binned") is False, "raw_binned")
        require(get_integer(raw, "copied_crop_x", "raw_crop_x_missing") == 0
                and get_integer(raw, "copied_crop_y", "raw_crop_y_missing") == 0,
                "raw_crop_origin_not_zero")
        require(get_integer(raw, "pixel_stride_bytes", "raw_pixel_stride_missing") == 2,
                "raw_pixel_stride_not_16bit")
        require(get_integer(raw, "format", "raw_format_missing") == 32,
                "not_camera2_raw_sensor_format")
        characteristics = get_obj(original, "selected_sensor_characteristics",
                                  "physical_characteristics_missing")
        require(get_integer(characteristics, "android.sensor.info.colorFilterArrangement",
                            "physical_cfa_missing") == 0,
                "physical_sensor_cfa_not_RB")

        return {
            "schema": "hasselblad-stage33-dng-capture-identity-v1",
            "status": "PASS_RECORDED_DNG_PHYSICAL_FRAME_BINDING",
            "matching_dng_hash_verified": True,
            "recorded_capture_physical_sensor_binding_proven": True,
            "recorded_capture_timestamp_and_frame_binding_proven": True,
            "recorded_raw_geometry_and_RGGB_agree": True,
            "independent_hardware_attestation_proven": False,
            "verification_source": "matched app-recorded CaptureEvidence sidecar and Stage32-read DNG",
            "original_DNG_or_capture_sidecar_modified": False,
            "private_hash_camera_id_timestamp_or_pixels_exported": False,
            "original_hasselblad_MAIN_pixel_equivalence_proven": False,
            "saved_photo_renderer_still_photon": True,
        }
    except Rejection as exc:
        return report_fail(str(exc))


def read_json(path: Path) -> dict:
    require(path.is_file() and path.stat().st_size <= MAX_JSON_BYTES, "input_json_missing_or_too_large")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Rejection("invalid_input_json")
    require(isinstance(data, dict), "json_object_required")
    return data


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage32-json", type=Path, required=True)
    p.add_argument("--capture-sidecar-json", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        a, b = read_json(args.stage32_json), read_json(args.capture_sidecar_json)
        result = proof(a, b)
    except Rejection as exc:
        result = report_fail(str(exc))
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    # A mismatch is not proof; keep strict shell CI checking.
    if result["status"] != "PASS_RECORDED_DNG_PHYSICAL_FRAME_BINDING":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
