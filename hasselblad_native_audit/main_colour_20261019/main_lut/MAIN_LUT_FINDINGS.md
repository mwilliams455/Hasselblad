# MAIN colour LUT: camera-driver submission contract

**Checkpoint:** 2026-10-19; Hasselblad X2D II 100C firmware 1.3.16.2.

The new evidence ties the saved-image `main_3dlut` parameters to the Eagle2 camera driver's LUT register writer. It establishes the exact pre-gamma and colour-table submission extents, their enable bits, and the shared component mapping with CCM and gamma. **It does not establish the MAIN table's RGB bank order, grid coordinates, input normalization, or hardware pixel interpolation.** A photographic LUT renderer remains blocked on those specific contracts.

This investigation extends the frozen `photographic_path` and `pixel_contract_20261019` checkpoints. Their complete-profile interpolation and display-only pixel-sampler tests were not repeated. No application source or saved photograph was changed.

## Source identity

| Input | SHA256 |
| --- | --- |
| Official full CIM | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` |
| `system/lib/modules/vcam_driver.ko` | `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e` |
| `system/lib/modules/cam_vreg.ko` | `26cf2246d56a36a5f7d107799ddced307ed94e53ac22c9928962a0fcff920ff6` |
| `system/lib/modules/kheaders.ko` | `b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b` |
| `system/lib64/librcam.so` | `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66` |
| `system/etc/iq/hb722_config.json` | `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286` |

Official download: <https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim>. Vendor files are supplied separately and are not part of this source bundle.

The kernel modules are AArch64 `ET_REL` objects. All module locations below are **section-relative offsets**, not loaded virtual addresses. Direct calls were resolved through `.rela.text` / `R_AARCH64_CALL26`; an unrelocated `BL` immediate was not treated as its runtime target. The local scripts save code hashes and derived metadata, not disassembly.

## Exact camera-component link

In `vcam_driver.ko`, `plat_eagle2_probe` requests the named platform resource `yuv_pp_base` at `.text+0x5c300`, maps it through `devm_ioremap_resource` at `0x5c310`, and stores the mapped address in the resource object's `+0x48` field. That resource object is saved at the platform context's `+0x2a0` field.

`plat_eagle2_probe_components` then assigns the following components to that same mapping:

| Component | Component ID | Probe call | Base assignment |
| --- | ---: | --- | --- |
| CCM | `0x4b` | `0x59fbc → ccm_probe` | `0x59fdc..0x59ff0`: mapped parent base `+0x2c000` |
| Gamma | `0x4d` | `0x5a0f4 → gamma_probe` | `0x5a114..0x5a128`: mapped parent base `+0x2e000` |
| 3D LUT | `0x4e` | `0x5a190 → lut_probe` | `0x5a1b0..0x5a1c0`: mapped parent base `+0` |

This is component address mapping, not a proof of their processing order. The physical parent base `0xf3200000` follows from matching the LUT writer's relative offsets to the independently recovered MAIN physical register descriptors: control at `+0x1c`, pre-gamma at `+0x7f7c`, and the colour table at `+0x8000`. No boot device tree was required for that cross-check.

`r2y_pad_set_fh_fmt` also has a resolved call to `lut_set_format` at `.text+0x6ea18`. `lut_set_format` (`0x32188`, 116 bytes) forwards the frame dimensions to `lut_set_size` (`0x3208c`, 96 bytes). That setter packs its two dimension arguments into a register at block `+0x14`; it does not choose RGB component order, precision, grid axes, or interpolation mode. The word “format” in this function name therefore cannot establish the pixel-domain contract.

## Pre-gamma and colour-table correspondence

The `librcam.so` register table at VA `0x4e6bd0` supplies the following MAIN descriptors. These are register metadata, not the vendor's colour-table contents.

| Parameter | Register ID | Physical address or parent | Extent or mask |
| --- | ---: | --- | --- |
| Control register | 2967 | `0xf320001c` | One register word |
| `tlut_en` | 2968 | Parent register 2967 | Bit 0, mask `0x1` |
| `enable_pre_gamma` | 2969 | Parent register 2967 | Bit 1, mask `0x2` |
| `module_en_lut` | 2970 | Parent register 2967 | Bit 2, mask `0x4` |
| Pre-gamma containing array | 2996 | `0xf3207f7c` | 33 register words |
| `pre_gamma` element | 2997 | Parent register 2996 | Position 0, mask `0x1fff` |
| `lut_data` | 2998 | `0xf3208000` | 6,144 words / 24,576 bytes |

The `pre_gamma` parameter is exposed by `DIQ_iq_main_3dlut_pre_gamma` (VA `0x337d58`) and its module getter (VA `0x337d98`); the frozen original-linker metadata probe already associates it with register 2997. Its descriptor declares `simple_lut_reg`, group `global`. The containing type-2 descriptor is at VA `0x4f2710`; the element descriptor is at VA `0x4f2720`.

The actual global configuration provides **33 pre-gamma values with minimum 0 and maximum 81**, but sets **`enable_pre_gamma = 0`**. The sRGB/P3 LUT parameter is independently enabled in the audited still modes. The pre-gamma array's JSON hash is `654c9c4d1d198cb28159f4041b3ea9e9eb4e07db5b417e54552886014a9af118`; its packed little-endian uint32 hash is `a00be6d9558f935928a2164ceae1672bd66aff09d1f4e47d7fa64adb536e47b8`. Its values are not included in this bundle.

The 13-bit element mask describes a register field. It does **not** prove a particular fixed-point interpretation, knot spacing, or a 16-bit-to-12-bit conversion. Because the audited configuration disables this local pre-gamma, applying it as a newly assumed shaper would also contradict the recovered settings. Static configuration does not rule out other runtime settings or modes.

## Original register-writer execution

`lut_set_lut_info` at `.text+0x31f48` is 324 bytes, with code SHA256 `d56ec8d675a29416ad0fca213aa4ff83e2b33cf5743453db1591fd7a045d3da4`. It has no relocations in its body. Its inspected argument contract is:

| Argument | Role in this original function |
| --- | --- |
| `x0` | Writable mapped register-block base |
| `w1` | Module-enable flag; zero/nonzero |
| `x2` | Two-pointer structure: pre-gamma input at `+0`, LUT input at `+8` |
| `w3` | Shadow identifier; updated only when the value fits in 8 bits |

Each input pointer addresses a uint32 enable flag followed immediately by its table words. With the relevant flags enabled, the function copies **33 complete uint32 words** to block `+0x7f7c..+0x7fff` and **6,144 complete uint32 words** to `+0x8000..+0xdfff`. It does not split components, change their order, rescale values, or sample an RGB input. It also writes enable/update bits and preserves/restores the DAIF interrupt masks.

`probe_main_lut_register_writer.py` reads and hash-checks the original module, then runs the complete original function body in **Unicorn AArch64 EL1h** with synthetic inputs and ordinary mapped RAM standing in for register addresses. It does not load a kernel module or access hardware.

**Result: all 32 cases passed.** The cases cover the three independent enable flags, valid/sentinel shadow identifiers, and both IRQ-mask entry states. Eight cases copy the full 6,144-word synthetic LUT, giving 49,152 word comparisons; eight copy the 33-word pre-gamma fixture, giving 264 comparisons. The fixture deliberately exercises all 32 bits of each submitted word.

Every case checks the complete 64-KiB register window against an independent final-state specification, exact write locations, source integrity, permitted data-read ranges, restored DAIF masks, and return to the sentinel. Source mappings are read-only and terminate at unmapped guard boundaries. This proves the **submission operations** on these inputs. It does not emulate ISP register masks, asynchronous update timing, pixel interpretation, or the hardware sampler.

The separate `cam_vreg.ko` path agrees at the generic transfer layer. `_sync_single_data_node` (`.text+0x11c0`, 692 bytes) forwards type-0 data-node addresses and word count to the selected writer. `_vreg_io_if_write32` (`0xfc0`, 200 bytes) transfers contiguous words in four-word, two-word, or one-word groups; its mask special case applies to a single register word. This provides no extra colour unpacking stage that could explain the MAIN grid representation.

## Bounded searches and remaining boundary

`kheaders.ko` contains an XZ-compressed kernel-header tar in `.rodata`: 3,778,928 compressed bytes, SHA256 `e0a474714b6980b41d9d7701a6bd768240a63d0889d8b37ae726f976d3199c27`, 9,329 archive members, and 30,049,604 regular-file bytes. The reproducible scan found no `MAIN_3DLUT` name or `0xf320....` address definition. Related hits consist of older ISP clock/reset definitions and display headers, including headers for multiple other platforms.

The Eagle2 display header explicitly declares a 6,144-word MIPI/HDMI TLUT. This is useful corroboration of a shared *extent*, but is **not** a link establishing that the camera MAIN block uses the display decoder's bank order or sampler. E4 display structures cannot resolve the Eagle2 MAIN format either.

The register-dump utility names `/system/etc/cam_dump_register.json`, but the file is absent from this extracted firmware. The utility is therefore not an available readable register-field specification. Its library hash and the exact embedded path location are retained in the static evidence.

The remaining renderer gate is precise: obtain a MAIN-linked definition or executable oracle for **component/bank layout, axis strides and grid knots, input normalization after photographic gamma, endpoint handling, and interpolation/rounding**. A hardware test oracle would need controlled asymmetric table/coordinate cases and off-grid samples, rather than natural photographs or a plausible-looking transform. If no MAIN CPU sampler is present, a documented Eagle2 hardware contract or an independent implementation tied to that exact block is needed. The already-proved display sampler can remain a separate oracle; matching the number of words does not authorize using it as the photographic renderer.

## Reproduce

Use separately extracted exact-hash firmware, Python 3, `pyelftools`, `capstone`, and `unicorn`. The static tool imports the already bundled inert parser at `../../photographic_path/inspect_iq_config.py`; its hash is recorded in the result. Both commands write only derived reports.

```sh
python inspect_main_lut_sources.py --firmware-root /path/to/extracted --output main_lut_static_evidence.json
python probe_main_lut_register_writer.py --firmware-root /path/to/extracted --output main_lut_writer_execution.json
```

`SOURCE_BUNDLE_MANIFEST.json` lists the allowlisted original scripts and derived reports. Original modules, configuration arrays, vendor headers, temporary instruction listings, and binaries are excluded.
