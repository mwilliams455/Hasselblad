# Stage 17 — original X2D II CCM numeric constraints and driver consumer audit

Scope: the **original** X2D II 100C firmware v1.3.16.2, `main_ccm.lmtx_fw` and `vcam_driver.ko`. This is an investigation of what the firmware **prepares for** the ISP; it is **not** a reproduction of what the ISP does to a pixel.

## Purpose

Stage 14 created a validated offline software-ISP research scaffold. The missing MAIN CCM pixel equation cannot be supplied by simply rearranging the six signed values per CCM group into a conventional 3×3 matrix. In the audited original firmware, each global still CCM source profile contains **16 repeated regions of six signed16 values**, and the two CCT-indexed high-ISO source banks are identical. This checkpoint independently rechecks that property from the original hashed IQ source and tests what it means after interpolating CCT and secondary bank weight. It also checks candidate producer/consumer functions in the exact hashed camera-driver `.ko`.

## Original input and provenance

- Official X2D II 100C 1.3.16.2 firmware SHA256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- Original `system/etc/iq/hb722_config.json`: `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286`.
- Original `system/lib64/librcam.so`: `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`.
- Original `system/lib/modules/vcam_driver.ko`: `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`.
- `main_ccm.lmtx_fw` packed 768 signed32 original-source slots: SHA256 `59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae641e`.
- Input IQ parsing uses the pre-existing inert, hash-pinned `photographic_path/inspect_iq_config.py`, rather than `eval` or a vendor service.

All original binaries and tuning arrays stay in an ephemeral CI runner. Published findings are boolean/pattern metadata, not original coefficients, original instructions, binary dumps, or a claimed licence to distribute vendor data.

## Executed work

`inspect_ccm_constraints.py` performs:

1. **Exact-source checks:** pins the original LIB, driver, IQ and parser SHA256 before analyzing the source.
2. **Original profile classification:** verifies eight 96-slot profiles, 16 exactly equal six-value groups in each, two equal high-ISO banks; identifies which of the six positions actually vary with CCT; groups temperature profiles by equality of all coefficients; classifies zero/nonzero/sign without retaining coefficients.
3. **Prepared-frame model:** independently reproduces previously verified `mm_mx_lerp_gap` fixed-point preparation (two-axis CCT/HISO; negative floor rounding) and verifies nine CCT samples × five secondary weights; asserts 16-region output invariance and high-ISO bank invariance for each case. This *only* tests the known numeric profile-preparation contract. The prior original-library mathematical equivalence is in `main_colour_20261019/ccm/ccm_prepare_original_execution.json`.
4. **IQ-mode inventory:** reports parameter names and whether `enable_lpf`, `enable_hue_mod`, `enable_desaturation` and `enable_level_ctrl` flags were zero in each encountered record. Does not export all profile data or other tuning parameters.
5. **Driver check:** reads `ccm_set_fn0_config`, `ccm_set_ig0_config`, `ccm_set_fmt` and any found `lite_ccm_set_info`/`ccm_get_dbg_info_by_mux`, verifies relevant exact symbol extents, and records only instruction counts, hash and whether multiply/call instructions occur. A register writer lacking pixel math is a **bounded negative result**, not proof of the absence of hardware CCM computation.

Run synthetic fixture without firmware:

```bash
python3 hasselblad_native_audit/isp_ccm_stage17/inspect_ccm_constraints.py --self-test
```

To run on the original firmware only after reconstructing the exact source:

```bash
python3 hasselblad_native_audit/isp_ccm_stage17/inspect_ccm_constraints.py \
  --firmware-root hasselblad_native_audit/firmware/extracted \
  --output /tmp/STAGE17_CCM_CONSTRAINTS.json
```

The matching GitHub Actions workflow downloads and hash-verifies the official CIM temporarily, uses the pinned existing unpacker, and uploads only a filtered JSON report.

## What the results can and cannot prove

- Equal rows in the **original global IQ table** do not prove the ISP ignores its 16-region mechanism, nor that runtime parameter overrides are impossible.
- Separate high-ISO source banks are equal **in this exact table**. Other modules, other IQ groups or dynamic frame controls may still respond to gain/ISO.
- Six signed coefficients **are not sufficient evidence for a 3×3 matrix, channel ordering, scale or a 2×3 equation**. The ISP also has separate nine-value fields in a different register range; no assumption about their combined formula is warranted.
- A successful interpolation check produces no photographic pixels and cannot validate the Lightroom/Hasselblad look.
- Neither the `lite_ccm` driver nor a DNG `ColorMatrix1/2` metadata getter may be treated as the saved-still MAIN CCM pixel oracle without proving the same hardware route.

## Next concrete steps

The hard remaining proof is an original **MAIN CCM input/output contract**: selector/group semantics, coefficient Q format, effective six-value pixel operation, channel coordinate domain, clipping, rounding, and relation to MAIN gamma/LUT. New work should pursue a directly matched Eagle2 hardware description or controlled ISP input/output probes. Once these exist, Stage14 can implement the pixel operation in a host-side software ISP and compare against it; only afterward should any colour transform be connected to the phone APK. HDR output is tracked separately as a possible single-exposure gain-map workflow.

Branch safety: only the `recovery/awb-rebuild-20261021` research tree changes; no APK, Stage8 JNI or Photon photographic rendering changes; `main` stays untouched.
