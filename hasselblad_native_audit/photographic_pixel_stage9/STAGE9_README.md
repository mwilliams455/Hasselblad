# Stage 9 — audited **display** 16³ format candidate, not saved-photo colour

**Project:** HasselbladPhoton. **Research-only.** Based on the prior X2D II
firmware 1.3.16.2 `pixel_contract_20261019` original AArch64 native execution.
The previously verified display library `libduml_hal.so`, SHA-256
`adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20`,
provided a native decoder and trilinear sampler oracle. The original library
was **not rerun during Stage9**; Stage9 uses the recorded 20 native outputs.

## Specific new result

An independently written, self-contained C11 `hb_display_lut16_node` decoder
and `hb_display_lut16_trilinear` sampler now reproduce the earlier **original
native DISPLAY-HAL** synthetic results. This is the `lookup_rgb_pixel_plt_fmt`
and bounded `do_3dlut_trans` path (`scale=1`, width 16, finite normalized
input). It does **not** establish that `MAIN_3DLUT` in the saved-image ISP
uses the same layout, samplers, input transfer or rounding. It has not been
connected to Android, camera RAW or saved-photo processing.

Packed display decoder, for r/g/b integer coordinates in 0..15:

```
q = 128*r + 8*g + (b//2)
shift = 16*(b & 1)
R = ((words[q]       >> shift) & 4095)/4095.0
G = ((words[q + 2048]>> shift) & 4095)/4095.0
B = ((words[q + 4096]>> shift) & 4095)/4095.0
```

All 6,144 uint32 words are required. Values 4096..65535 in either 16-bit
lane's reserved bits are masked. The sampler uses `position = input*15`,
eight surrounding nodes, and trilinear weighting in double precision for
finite RGB in `[0,1]`. It forbids photographic headroom/negative signals;
unsupported width or scale have no interface and cannot be silently assumed.

## Tests (synthetic only)

Run from any directory:

```
python3 hasselblad_native_audit/photographic_pixel_stage9/tests/test_display_lut16.py
```

The test compiles C with the host C11 compiler. It constructs the original
probe's intentionally asymmetric **synthetic** 16³ fixture including nonzero
reserved high nibbles. It verifies each of 4,096 grid nodes and 12,288
individual channel values. It compares 20 trilinear results with exact archived
original native outputs and checks in-place input/output, nonmutation, invalid
coordinates, invalid size, bad finite/range values and source/output overlap.
Stage9 adds ten negative/nonmutation checks.

Observed local result:

- **4,096/4,096 nodes** match the analytical original fixture, max error 0;
- **20/20 original-native test vectors** match, max absolute difference
  `1.1102230246251565e-16` (tolerance `1e-12`);
- **10/10** negative argument and unchanged-output conditions pass;
- Source LUT remains unchanged. No original vendor data/phone images included.

## Next evidence gate — MAIN vs DISPLAY

The prior MAIN register contract: register ID **2998**, virtual register offset
`0x16b80`, physical LUT address `0xf3208000`, 6,144 words. The original
`DjiAdj_Calc_LutMemCopy` preserves those words with no CPU reorder. Matching
size with this display format is **not sufficient** to claim format equality.
Before using the display decoder on a prepared MAIN profile, establish at
least one of: a shared hardware format declaration; actual MAIN consumer
instruction path relating banks/axes to input/output; or a controlled MAIN
hardware pixel readout that distinguishes this candidate from alternative
swizzles/interpolation rules. Independently establish MAIN_CCM and
MAIN_GAMMA ordering and the gamma-to-LUT input domain; the prior native gamma
knot and CCM coefficient work did not prove per-pixel transfer.

A verified MAIN layout would still require the Xiaomi/other phone sensor's
own calibrated camera-to-working transform and Stage7 independently labelled
neutral reference acceptance, then one-time WB and headroom-safe demosaic.

**Git/privacy:** No vendor firmware/CIM, 3D LUT payload, camera DNG, original
calibration or user/private scene data is committed. Existing app version 27186
remains unchanged and continues to use Photon photographic colour.
