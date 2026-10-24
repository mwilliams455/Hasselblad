# Stage59: native RAW code units and clipping provenance

Stage59 establishes a bounded input contract for the original highlight stage.
It does not change the renderer or produce an APK. The current device build
remains **Stage58, `0.1-hb-rawprep58` / 27197**, with the Stage56 private profile.
No scene-specific parameters were fitted.

[Stage60](../phocus_bayer_stage60/README.md) continues this audit through the
fast Bayer/highlight/Bayer pixel stages and executes the downstream original
CPU gradient demosaic in a bounded harness. The full native DNG import and
gain-map path remain unresolved.

The supplied Stage58 report selects `automatic_dng_preparation`, automatic LUT
3550 K, native finishing on and highlight reconstruction off. All eleven RAW
audit counters agree exactly with the retained host report. The device has not
exported pixels for a host comparison; counter agreement is not pixel equality
or proof of a physical Hasselblad colour match. The reported 5,503 ms total and
4,371 ms preparation are one run, not a performance benchmark.

## Native graph result

The original `AddSingleshotRawFilters` body was executed in 864 synthetic cases
with a fixed camera context and controlled noise/lens services. Inputs vary four
black offsets, nine source-clipping overrides, six WB permutations, two source
scalar sets and two independent reference levels. Graph ownership is mocked;
the full RAW pixel graph is not executed.

For a positive source-clipping override, each highlight clipping code is

```
clamp(source_clipping_override - black_offset, 0, 65535)
```

For a nonpositive override, the builder calls the original camera-specific
fallback and subtracts black from each returned channel. All 192 fallback
cases pass; the private fallback values are not exported. The separate integer
reference is also decremented by black, but does not supply the clipping
triple. Tested source scalar changes do not alter that triple.

The bounded sequence is orientation, optional black subtraction, fast Bayer
interpolation, highlight reconstruction, conversion back to Bayer and final
demosaicing. Highlight gains are process gains normalized by their maximum;
final demosaic gains are unity. This is the noise-disabled branch, not every
native operating mode.

The original black-subtraction constructor and complete CPU pixel body were
also executed: **6,288 channels across twelve cases match exactly** against
`max(sample - black, 0)`. Cases cover one/three channels, two rows, boundary
values and synthetic random codes. There is no white-range normalization in
that filter. Buffer ownership is a fixture and memory guards pass.

Six executions of the original base builder insert a `16 - bit_depth` shift
for tested depths 8, 10, 12, 14 and 15, and no shift for 16. This establishes
the graph request only. It does not prove how the full source-description
constructor translates a particular file's black/white metadata into these
code units. Static inspection shows conditional DNG WhiteLevel handling; it is
not an unconditional, independently executed import rule in this audit.

Some synthetic clipping overrides fall at or below black. The builder emits
zero clipping codes in 216 cases. Those codes were **not** passed to the
highlight primitive, whose audited valid domain requires positive limits.

## A scale change is not a general colour correction

Twenty-four original double-scalar cases compare a common rescaling of pixels
and clipping limits. They include 8,640 channels over six WB permutations and
four synthetic limits. Away from exact clipping, maximum difference after
rescaling output back is **4.44e-16**. Independent highlight equations match
the original scalar results to the same tolerance.

There is an explicit boundary exception. With synthetic clipping code 60,000,
`(limit / 65535) * reciprocal(limit / 65535)` evaluates just below one. A sample
exactly at the limit can therefore enter the interior branch in one encoding
and the edge branch in another. Maximum tested difference is **0.00107939**
in normalized source output. The receipt retains a synthetic witness. This is
not an sRGB difference or evidence about its prevalence in photographs.

Eighteen targeted RGB16 CPU cases at clipping and its immediate neighbours
match the existing portable C implementation exactly, **486 channels**. The
boundary behavior is preserved and reported, not silently patched. Deliberately
changing clipping units without changing pixel units produces a large mismatch
in the negative control (maximum 0.24157).

Consequently, changing the phone's common normalization alone is not supported
as a general improvement. A ceiling of 65,535 can be consistent with a uniformly
normalized input; it is not inherently wrong merely because the original
graph uses source codes. This result does not establish equivalence under
channel mixing, unequal channel scaling, spatial gain maps, intermediate
clipping or a different demosaic. Stage57's sensor-basis dependence remains.

## DNG gain-map boundary remains distinct

The original `CRawImageFile::OpcodeLists` method was executed with absent
header/tag fixtures. When a header exists, it queries tag **51022
(OpcodeList3)**. Its returned container is empty under this fixture; no opcode
payload or full decoder is executed. Static tracing connects this accessor's
vector to the source description and RGB lens-filter construction, but does
not establish every native decoder path or whether a correction is enabled.

The retained phone DNG instead contains **four GainMap opcodes in tag 51009
(OpcodeList2)**, with neither OpcodeList1 nor OpcodeList3 present. This was
verified from the private DNG's opcode IDs without exporting gain payloads.
The similarly named HDR gain-map functions are not evidence about these RAW
shading maps. This audit cannot justify relocating or deleting the phone maps.

Stage58 already measures 22,863 gain-map-clipped sites below recorded WhiteLevel
in its decoded-row scope. A global rescaling after that clamp cannot restore
the distinctions it discarded. Recorded WhiteLevel remains metadata, not a
measurement of physical sensor saturation.

## Decision and next boundary

Keep Stage58's DNG-preparation comparison as the current reconstruction-off
baseline. It is a controlled baseline, not a verified superior photograph.
Do not introduce a manual highlight scale or a new look adjustment from this
audit. No additional phone installation is needed for Stage59.

The next implementation gate is an independently checked input path that tracks
black-subtracted samples, clipping provenance and gain-map effects through the
fast Bayer/highlight boundary. Full source-description/decode behavior and
sensor adaptation still need validation. Physical cross-camera accuracy also
requires controlled reference images and held-out scenes; this audit supplies
neither. Capture continues using Photon and full Phocus equivalence is false.

## Reproduce privately

```sh
python3 hasselblad_native_audit/phocus_rawdomain_stage59/audit_rawdomain59.py \
  --apk /private/original.apk --safe-receipt /private/native-domain59.json

python3 hasselblad_native_audit/phocus_rawdomain_stage59/audit_device59.py \
  --dng /private/input.dng \
  --device-report evidence/stage59/STAGE58_DEVICE_BASELINE.json \
  --host-report evidence/stage58/STAGE58_SAVED_DNG.json \
  --safe-receipt /private/device-reconciliation59.json
```

These reuse the Stage52/53 bounded ARM64 runner and its dependencies (NumPy,
Unicorn, Capstone, ELF tooling; GCC for the existing C-port boundary check).
The metadata reconciliation also needs tifffile. Original APK, DNG, private
profiles, private hashes, extracted code and pixel buffers remain outside git,
CI and APK. Only independently authored audit source and aggregate receipts
are published in `evidence/stage59`.
