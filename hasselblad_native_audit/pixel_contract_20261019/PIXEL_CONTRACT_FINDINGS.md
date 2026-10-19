# X2D II pixel-contract investigation — 19 October 2026

## Result and exact scope

**Original X2D II firmware code now supplies a verified CPU oracle for a packed display LUT decoder and trilinear sampler. The relationship between this display format and the camera's saved-image `MAIN_3DLUT` remains unproved.** No camera LUT was applied to a photograph, no image was edited, and no Photon source or APK was changed by this investigation.

Two separate boundaries advanced. First, original linker-relocated camera metadata independently confirms that `MAIN_3DLUT` consumes a 6,144-word hardware table, and its audited copy path preserves the prepared packing. Second, original display-HAL functions executed successfully against asymmetric synthetic fixtures, establishing their precise component order, grid order, 12-bit packing, and normalized trilinear behavior. A matching byte extent is insufficient to connect those facts into a photographic renderer.

This directory is a new research checkpoint. The earlier `../photographic_path` profile-preparation proof was read as evidence and left unchanged.

## Firmware identity

All addresses below are ELF virtual addresses in these exact files, not offsets that can be reused with another firmware version.

| Input | SHA-256 |
| --- | --- |
| Official X2D II 100C 1.3.16.2 CIM | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` |
| `system/lib64/librcam.so` | `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66` |
| `system/lib64/libduml_hal.so` | `adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20` |
| `system/etc/iq/hb722_config.json` | `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286` |

The reference environment uses the previously extracted Android 9 / API 28 AArch64 Bionic and linker. Native execution here means original AArch64 instructions under QEMU user emulation with that runtime. It does not claim that the display library has run in the Photon APK on the user's phone.

The vendor input can be obtained independently from the [official firmware URL](https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim). No original vendor payload is included in this source/evidence allowlist.

## 1. Saved-image MAIN_3DLUT hardware boundary

`inspect_lut_descriptor.c` loads the exact original `librcam.so` and reads only bounded, relocated metadata. It invokes no camera processing function. `native_descriptor_result.json` records exit 0 and empty stderr.

| Observed item | Value |
| --- | --- |
| Main LUT non-vreg parameter record | `0x5927c8` |
| IQ getter | `DIQ_iq_main_3dlut_lut_data`, `0x337dd8` |
| Module getter | `DIQ_mod_main_3dlut_lut_data`, `0x337e18` |
| Register ID | `2998` |
| Register descriptor | `0x4f2730` |
| Descriptor type | `1`, memory LUT |
| Vreg byte offset | `0x16b80`, decimal 93,056 |
| Physical LUT address | `0xf3208000` |
| Descriptor word count | `6144`, or 24,576 bytes |

The mapping follows audited original consumers `DjiIsp_Reg_GetLut` (`0x251a18`) and `isp_drv_reg_get_lut` (`0x277140`). Their type-1 descriptor reads identify a virtual offset, physical address and word count. Other descriptor types have different meanings: the regular type-3 fields are not misreported as addresses or table sizes.

`DjiAdj_Calc_LutMemCopy` (`0x3b30b0`) copies the relevant memory payload in original order. Its `mem_cfgen = 1` path transfers 64-bit chunks; no per-component unpacking or grid reordering appears in that copy. The earlier proven `mm_mx_lerp_vec_mix2` therefore produces the representation submitted to this hardware interface. `post_scap3_calc_3dlut` (`0x2f2d08`) and `post_hdr_calc_3dlut` (`0x301b00`) also use the same main-parameter group and calculation dispatcher; their inspected code prepares parameters rather than sampling RGB pixels.

This is independent support for the previous profile size: eight CCT/gamut profiles occupy 49,152 words in the IQ configuration, and each selected profile occupies 6,144 words. It does **not** establish how MAIN hardware maps those words to pixel coordinates, interprets the input transfer function, or interpolates between knots.

## 2. Original display decoder and sampler execution

The relevant code belongs to `libduml_hal.so`. An embedded source path at VA `0xaeaeb` is `hardware/dji/duml/hal/disp/disp_3dlut_tools.cpp`. Related conversion code identifies `disp_3dlut_transformer.c`. This is explicit display provenance.

| Function | VA | Bytes | Proof obtained |
| --- | --- | --- | --- |
| `lookup_rgb_pixel_plt_fmt` | `0x74fb0` | 148 | Original decoder executed at all 4,096 valid grid nodes |
| `do_3dlut_trans` | `0x72dc0` | 1,564 | Original sampler executed on 20 synthetic normalized triples, calling the original decoder |
| `get_plt_fmt_unit_3dlut` | `0x74e50` | 348 | Original identity-table generator executed, then all nodes decoded |
| `set_rgb_pixel_to_plt_fmt_lut` | `0x74c88` | 452 | Statically audited and exercised through the original identity generator |

Exact mangled export names, symbol extents, code hashes, dependencies, and ELF load segments are retained in `pixel_contract_static_evidence.json`. The probe uses `dlsym`, verifies the exact pathname and `dladdr` symbol identity, and checks the expected virtual address for each called export. This ELF's first `PT_LOAD` starts at VA `0x2000`; the probe accounts for Bionic returning the first mapped address in `dli_fbase`.

### Verified display format

For valid integer coordinates `r`, `g`, `b` in **0 through 15**:

```text
q = 128*r + 8*g + floor(b/2)
shift = 16*(b & 1)
R = ((words[q       ] >> shift) & 4095) / 4095.0
G = ((words[q + 2048] >> shift) & 4095) / 4095.0
B = ((words[q + 4096] >> shift) & 4095) / 4095.0
```

There are three 8,192-byte component banks. B varies fastest, G next, R slowest. Even and odd B occupy the low and high halfwords respectively; only 12 bits in either halfword contribute. The setter's diagnostic index arguments identify the third coordinate reference as R, second as G, first as B. The original identity generator and the sampler's callback argument construction independently agree with that order.

The integer decoder ABI is equivalent to:

```c
struct PixelRGB { double r, g, b; };  /* 24 bytes */
PixelRGB *lookup(const void *words,
                 const size_t *b, const size_t *g, const size_t *r,
                 PixelRGB *out);
```

The function returns `out`. It has no external calls. Its only numeric global used by the successful path is the double constant 4095 at VA `0x9a590`.

The audited setter has a suspicious inclusive bound that permits coordinate 16 although its packing uses the 16-wide strides above. The test deliberately exercised endpoints 0 and 15, with width 16, and never invoked it at index 16. This evidence provides no basis for treating the format as a 17-cube.

### Verified sampler subset

The tested ABI is equivalent to:

```c
int transform(PixelRGB *in_out, const int32_t *scale,
              lookup_fn original_lookup, const void *words, size_t cube_width);
```

The proved subset uses finite RGB doubles within `[0,1]`, `scale = 1`, and `cube_width = 16`. It forms coordinates `15*R`, `15*G`, and `15*B`, samples the eight surrounding knots through the original lookup callback, clamps upper grid indices to 15, and accumulates trilinear weights in double precision. It returns 0 and overwrites the three doubles. The synthetic cases include all cube vertices, asymmetric on-grid values, fractional values, exact upper coordinates, and values just below the upper endpoint.

This establishes a normalized numeric domain for this display utility. It does not establish whether the values in the photographic MAIN stage are linear-light RGB, gamma-encoded RGB, another shaped domain, or the output of a particular CCM. An implementation using this contract must retain the proved parameter restrictions rather than generalizing the callback to another cube size or accepting untested scaling.

### Execution results

`display_sampler_native_execution.json` records a successful original-runtime execution, exit 0, empty stderr:

| Test | Coverage | Result |
| --- | --- | --- |
| Asymmetric synthetic decoder fixture | 4,096 nodes / 12,288 components | All exact; maximum absolute error 0 |
| Original trilinear sampler with original decoder callback | 20 triples / 60 components | All within `1e-12`; observed maximum error `1.1102230246251565e-16` |
| Original identity generator and decoder | 4,096 nodes / 12,288 components | All exact against the specified 12-bit quantization |

The asymmetric fixture uses different coordinate-dependent formulas in each component, including nonlinear and wrapped values. It catches bank, axis and parity swaps that an identity table alone might miss. Its unused high nibbles are deliberately nonzero; the decoder correctly ignores them. All fixtures are generated by the original audit source and contain no camera LUT values.

The table occupies exactly six 4-KiB pages, with inaccessible guard pages on both sides. During decoding and sampling it is read-only. Output structures have canaries before and after their 24-byte payloads. Return pointers, return statuses, finite outputs, canaries and source integrity all passed. These checks validate the bounded fixture and observed calls; they are not a claim about arbitrary malformed inputs.

## 3. Why the MAIN/display link remains unresolved

A dynamic-symbol survey of all **374 ELFs under extracted `system/lib64`** found the exact decoder, sampler, setter and identity-generator names only in `libduml_hal.so`. Related cube conversion exports also appear in `weston/eagle-backend.so`. No direct dynamic import of these helpers was found in `librcam.so` or the other camera libraries in this survey. This bounded survey cannot exclude indirect calls, inlined copies or a shared hardware specification.

The configuration comparison adds no byte-identity link. All eight MAIN 6,144-word chunks differ from the existing LCDC and pyramid chunks. `asset_format_relationship.json` retains only hashes, counts and equality results. It does not contain LUT payloads or assume that chunking alone establishes a format.

The camera and display code are on the same platform, use the same 24,576-byte extent, and are consistent with 12-bit paired components. These observations make the display decoder a concrete candidate for the MAIN packing. The missing evidence is a common format declaration, a packing conversion on a demonstrated MAIN consumer path, an original MAIN software sampler, or a controlled hardware pixel result that distinguishes competing layouts and interpolation rules.

The previously identified active still configuration also includes `MAIN_CCM` and `MAIN_GAMMA`; knowing a LUT layout would not resolve their calibration and transfer-function contract. The separately named `MAIN_HNCS` remains bypassed in those particular configured still segments, as documented in the frozen photographic-path report.

## 4. A colour-matrix lead that did not establish a photographic stage

The `camrgb_to_xyz_d65_output` diagnostic is reached from `_ColorMatrix_Func` at `0x395228`, whose embedded source is `adj_mod_metadata_prores_raw.c`. It calls `DjiMetadata_ProresRaw_GetCcmByCct` at `0x3c4140` and writes matrix metadata. The audited helper interpolates between two nine-float matrices in reciprocal colour temperature, with endpoint handling. This is a metadata calculation, not an observed saved-still RGB-to-XYZ pixel transform. No original execution or pixel-rendering claim was made for this lead.

## 5. Concrete next implementation and next evidence gate

The next portable primitive that has an actual original-code oracle is the **display-format node decoder**, followed by the bounded trilinear sampler. They can be added to an isolated mathematical test module, with the synthetic fixtures in this checkpoint as an oracle. A private original-code execution adapter could start with the 148-byte decoder, whose only numeric global is 4095. Such work must be labelled as a format/CPU compatibility test until the MAIN connection is established.

Before using the camera profile on saved Photon pixels, the specific missing gate is to establish **MAIN's bank/axis packing, knot coordinates and transfer domain, and hardware interpolation/rounding**. The proved camera register ID 2998 / physical address `0xf3208000` and unchanged copy path give a concrete target for a platform format declaration or controlled MAIN input/output capture. The display sampler supplies an executable candidate model against which such evidence could be compared. Existing table counts and visually plausible output would not supply that proof.

Once the MAIN contract has evidence, the phone's own RAW calibration and working-space conversion must feed that established domain. The user's supplied phone DNG audit is separate and does not yet provide a measured phone-to-Hasselblad sensor fit.

## Reproduce

Inputs are the exact previously extracted firmware, Android NDK compiler, QEMU AArch64 user emulator, and Python with `pyelftools`. The optional IQ comparison uses the exact frozen `inspect_iq_config.py` parser (SHA-256 `0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec`). It parses the vendor config as inert data and never evaluates its contents as code.

From the audit root, with task-specific paths set appropriately:

```sh
python pixel_contract_20261019/replay_descriptor_probe.py \
  --firmware-root firmware/extracted \
  --clang "$audit_clang" --qemu "$audit_qemu" \
  --output pixel_contract_20261019/native_descriptor_result.json

python pixel_contract_20261019/replay_display_sampler.py \
  --firmware-root firmware/extracted \
  --clang "$audit_clang" --qemu "$audit_qemu" \
  --output pixel_contract_20261019/display_sampler_native_execution.json

PYTHONDONTWRITEBYTECODE=1 python pixel_contract_20261019/inspect_pixel_contract.py \
  --firmware-root firmware/extracted \
  --iq-parser photographic_path/inspect_iq_config.py \
  --output-directory pixel_contract_20261019
```

The native runners compile API-28 AArch64 probes, enforce the library hash, use the original extracted linker/Bionic with `LD_LIBRARY_PATH=firmware/extracted/system/lib64`, disable core files, and bound CPU and wall-clock time. No stub replaces any of the called original exports or their lookup callback. `libduml_hal.so` directly needs `libduml_util`, `libduml_osal`, USB/usbmux, cutils, ion, log, libc++, libc, libm and libdl; the exact dependency list is in the static evidence JSON. This reference-runtime load does not establish that the full dependency closure is suitable for loading into a modern Android app.

`SOURCE_BUNDLE_MANIFEST.json` is the allowlist for this checkpoint. It includes original audit source, reports and hash/count/result evidence. It excludes vendor firmware, configs, original LUT bytes, extracted libraries, compiled probes and disassembly dumps.
