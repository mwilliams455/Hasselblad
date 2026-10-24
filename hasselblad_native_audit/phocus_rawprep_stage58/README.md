# Stage58: RAW preparation and clipping provenance

Stage57's device report confirms `automatic_colour_only`, selected LUT 3550 K,
native finishing enabled and reconstruction off. Stage58 follows that working
comparison upstream. It adds **Show DNG preparation**, using the same automatic
LUT, DNG WB/matrix, film and finishing as Stage57's reconstruction-off view.
Only input preparation differs. Existing views remain available and byte-exact
on the retained host DNG. Capture still uses Photon. No photographic parameter
is fitted and no new private profile is needed.

## Findings and correction

The old preview divides each Bayer site's black-subtracted value by that site's
own white-minus-black range. It also lets negative and above-range values reach
gain maps and interpolation, with a final RGB clamp. The new comparison uses a
common range for the single sample plane, `WhiteLevel - max(BlackLevel)`, and
clips range-mapped Bayer values to 0..1 before gain maps and demosaicing.

These choices follow Adobe's published integer-RAW processing model in
[dng_linearization_info.cpp](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_linearization_info.cpp).
The [GainMap implementation](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_gain_map.cpp)
also applies an upper ceiling after each map. Therefore simply removing that
ceiling is not established as a DNG correction. The cited SDK source is a
published 1.4-era implementation, not an executed SDK oracle.

Stage58 keeps the previous four-term double gain interpolation with float stores
and the same diagnostic bilinear demosaic/RGB16 encoding. It does **not** claim
bit-exact Adobe SDK or Phocus decoding. The restricted uncompressed RGGB DNG
format, crop, calibration and opcode checks are retained.

The previously reported zero `input_over_unity_channels_clipped` was counted
only after gain maps and demosaicing. It never established absence of earlier
clipping. New counters distinguish metadata white-level crossings, initial
range clamps, map clipping events, unique map-clipped sites and final preview
channels. WhiteLevel is file metadata, not independently measured saturation.

The optional diagnostic retains signed, unclamped gain-scaled float RGB before
RGB16 encoding. It includes noise and values originating from saturated sites;
it is **not recovered highlight detail** and is never sent to the display path.
This preserves information for the next domain investigation without inventing
a highlight scale. The new rendered comparison still bypasses highlight
reconstruction, so it does not resolve Stage57's nonlinear adaptation finding.

## Synthetic validation

Twelve generated DNGs at four preview limits make 48 cases and 174,132 RGB
channels. Cases include equal/unequal/scalar black levels, both TIFF byte orders,
multiple strips, four orientations, below-black and white-level boundary
patches, spatial gains below and above unity, and overlapping maps that clip
then attenuate. A full-frame NumPy reference is evaluated independently of the
Java row cache. Corrected RGB16, diagnostic float values and counters all match
exactly. Legacy RGB16 matches its independent reference and the legacy API.
Rejection/cancellation checks pass, as do all prior Stage42/43/48/54/55/56/57 host
checks. No private data is used by CI.

## Retained DNG: execution and effect, not photographic accuracy

The selected temperature remains 3550 K. All 2,359,296 corrected preparation,
diagnostic float, colour and finished channels match their respective host
references. The previous Stage57 direct automatic result is byte-identical.

| Counter | Unique decoded preview rows | Whole RAW, offline audit |
| --- | ---: | ---: |
| Sites inspected | 9,433,088 | 12,582,912 |
| Below black | 5,641 | 6,065 |
| At or above recorded white | 78,824 | 97,307 |
| Gain-map clipped sites | 101,687 | 128,759 |
| Gain-map clipped sites below recorded white | 22,863 | 31,452 |

Counters refer to different domains and must not be added as disjoint groups.
In particular map clipping can also involve sites already at WhiteLevel. The
app counts all columns of unique rows it decodes for the preview; it does not
claim a whole-RAW scan or just the sites contributing to displayed pixels.

This DNG has equal black levels. Its visible comparison therefore primarily
exercises the corrected lower-clipping order. 4,593 prepared RGB16 channels
change; 3,003 of 786,432 displayed pixels differ by more than two codes in at
least one channel (0.382%). Mean absolute channel change is 0.00968/255; maximum
is 18/255. These are differences, not accuracy scores. They do not establish a
closer physical Hasselblad match and did not determine the algorithm.

## Build and device check

Build `0.1-hb-rawprep58` / `27197`, same app identity/signature and both ABIs.
Keep the Stage56 profile. Open the saved DNG, cycle past **Automatic colour
only** to **Show DNG preparation**, then copy the report. Expected:
`displayed_preview: automatic_dng_preparation`, native finishing true,
highlight reconstruction false, and the same selected automatic LUT.

Stage58 is host-tested until the new device report arrives. General photographic
validation still needs held-out scenes and controlled reference renders. The
next highlight task is to establish original source normalization, clipping
units and gain-map placement before passing a new domain into the nonlinear
primitive. Keeping a float diagnostic does not itself solve that boundary.

## Reproduce

```sh
python3 hasselblad_native_audit/phocus_rawprep_stage58/check_host58.py --work /tmp/hb58
```

For a private audit, `Stage58DngCheck` takes DNG, existing Stage56 profile,
private output directory and Stage57 direct finished-RGB16 file.
`audit_saved58.py --help` compares the dumps against independent full-frame
preparation and colour/finishing references. Original APK, profiles, DNGs,
private hashes, buffers and derived samples stay outside git, CI and APK.
