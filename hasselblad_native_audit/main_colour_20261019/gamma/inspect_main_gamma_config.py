#!/usr/bin/env python3
"""Inspect exact still MAIN_GAMMA config as inert data; retain no LUT arrays."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PARSER_SHA = "0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec"
CONFIG_SHA = "2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286"
SCHEMA_SHA = "59ec3b0d019b9e8873f3d005c041b4e3ca1a2b930c503c110c51531f8bd30e40"
CURVE_SHA = "5c5f69a4087f0aee9ee0068c8687b13e0922dc228550349398a019e468dbfb6f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_metadata(values):
    if not isinstance(values, list) or not values or any(type(v) is not int for v in values):
        raise ValueError("Expected nonempty integer data array")
    return {"count": len(values), "minimum": min(values), "maximum": max(values),
            "all_zero": all(value == 0 for value in values),
            "values_json_sha256": hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()}


def scalar(values):
    if not isinstance(values, list) or len(values) != 1 or type(values[0]) is not int:
        raise ValueError("Expected one scalar config value")
    return values[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.firmware_root / "system/etc/iq/hb722_config.json"
    schema_path = args.firmware_root / "system/etc/iq/config.fbs"
    parser_path = Path(__file__).resolve().parents[2] / "photographic_path/inspect_iq_config.py"
    for path, digest in ((config_path, CONFIG_SHA), (schema_path, SCHEMA_SHA), (parser_path, PARSER_SHA)):
        if sha(path) != digest:
            raise ValueError("Pinned input mismatch: " + path.name)
    spec = importlib.util.spec_from_file_location("main_gamma_inert_iq_parser", parser_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.read_config(config_path)
    modes = []
    for index, data in enumerate(config["iq_table"]["data"]):
        mode = data.get("mod_iq_mode")
        if mode not in ("still0", "still1", "still2", "still3", "still4"):
            continue
        if len(data["main_gamma_normal"]) != 1 or len(data["main_gamma_common"]) != 1:
            raise ValueError("Unexpected still gamma profile count")
        normal, common = data["main_gamma_normal"][0], data["main_gamma_common"][0]
        curve = array_metadata(normal["gamma_lut"])
        if curve["count"] != 257 or curve["values_json_sha256"] != CURVE_SHA:
            raise ValueError("Pinned still gamma table mismatch")
        modes.append({"mode": mode, "data_index": index, "positive_curve": curve,
                      "negative_curve": array_metadata(normal["gamma_minus_lut"]),
                      "lut_div": normal["lut_div"], "lut_div_minus_scale": scalar(normal["lut_div_minus_scale"]),
                      "controls": {name: scalar(common[name]) for name in ("enable", "knee_en", "dither_enable", "dither_seed")},
                      "knee_clip": scalar(normal["knee_clip"]),
                      "dither_key_metadata": {name: {key: value for key, value in array_metadata(common[name]).items()
                                                      if key in ("count", "values_json_sha256")}
                                              for name in ("dither_key_r", "dither_key_g", "dither_key_b")}})
    if [item["mode"] for item in modes] != ["still0", "still1", "still2", "still3", "still4"]:
        raise ValueError("Still mode inventory mismatch")
    if any(item["lut_div"] != [2, 2, 3, 4, 5, 6, 7] for item in modes):
        raise ValueError("Unexpected division controls")
    normal_module = config["iq_table"]["module"]["main_gamma_normal"]
    selected_module_metadata = {name: {key: value for key, value in normal_module[name].items()
                                      if key in ("type", "group", "total", "mem_cfgen")}
                                for name in ("gamma_lut", "gamma_minus_lut", "lut_div", "lut_div_minus_scale")}
    result = {"result": "pass", "firmware": "X2D II 100C 1.3.16.2", "config_sha256": CONFIG_SHA,
              "schema_sha256": SCHEMA_SHA, "parser_sha256": PARSER_SHA, "tool_sha256": sha(Path(__file__)),
              "method": "Exact hash-pinned config parsed as inert data; only protocol controls, counts, ranges and table hashes retained",
              "still_modes": modes, "module_metadata": selected_module_metadata,
              "limits": "Static selected configuration, not a capture trace; curve word range does not establish the hardware pixel input/output precision"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"result": "pass", "still_modes": len(modes), "curve_sha256": CURVE_SHA, "output": str(args.output)}))


if __name__ == "__main__":
    main()
