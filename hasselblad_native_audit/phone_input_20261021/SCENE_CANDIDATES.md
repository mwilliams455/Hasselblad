# Phone scene-candidate bridge — 21 October 2026

The saved Native1C RAW now reaches owned scene weighting, connected filtering, candidate accumulation and candidate optimization using its own original Camera2 calibration. This is the first phone-data candidate bridge. It is a bounded, stateless ordinary-candidate route, not a call to the complete `hb_run_automatic` controller and not a calibrated shipping AWB profile.

## What is connected

`hb_phone_scene.c/.h` accepts a validated original-metadata temperature descriptor, an explicit experimental policy and the existing32×32 RAW grid. It generates81 temperature points from2000 to10000 K, converts every gain triple to **green=4096**, and classifies each eligible block by an exhaustive nearest-point search. The temperature leaf normalizes to the smallest channel, whereas the RAW ratios use green; using the temperature triple directly would put the locus in the wrong coordinate system. Integer64-bit rescaling fixes that interface mismatch without altering either existing module.

The phone classification is deliberately explicit adaptation code. It does not call the original sparse LUT expansion/search, assume a unimodal distance curve or treat the phone's matrix-derived locus as an IMX861 calibration table. Full81-point sampling avoids a new sparse interpolation approximation. The existing owned numerical kernels then run in this order:

1. `hb_candidate_weight`: uniform temperature prior with the recovered distance taper and integer weight handling.
2. `hb_scene_filter`: the recovered component filter, including removal of groups with three or fewer blocks.
3. `hb_candidate_accumulate_with_model`: the ordinary weighted candidate with an explicit minimum support threshold.
4. `hb_scene_optimizer`: one eligible measured candidate, no fallback candidate.
5. `hb_phone_temperature_from_gain`: calibrated CT/tint interpretation and inverse residual validation before publishing a diagnostic result.

The first four are reused unchanged. Accumulation's internal temperature mode is the recovered locus mode0; the final published CT/tint comes from the separately validated phone matrix model. No firmware initializer, vendor function, vendor config, private device table or HAL neutral is used to select the candidate. The work context starts from zero for every frame and its full-automatic initialization marker remains unset.

## Policy and numerical bounds

The API has **no default policy**. The caller must explicitly supply locus-centre tint, radius in green-normalized Q12 gain space, neighbour factor, minimum supporting blocks, and a normalized Bayer-brightness admission interval. These are experimental controls, not values supplied by Camera2 or discovered as ground truth. This verifier uses six clearly labelled test radii and does not select one for production.

The curve centre permits finite tint within±100; every generated point must remain within the temperature leaf's accepted gain domain. Radius is1..4096 and neighbour factor is1..255, no larger than the radius. Minimum support is4..1020 in multiples of four, matching the existing fraction/256 representation for1024 blocks. Brightness bounds are finite, ordered and within[0,1]. That brightness is the RAW adapter's arithmetic Bayer mean, not CIE luminance, scene EV or a vendor exposure measurement.

Blocks with existing RAW rejection flags remain excluded. Additional admission gates reject brightness outside the stated interval and gains above32767, because the retained connected filter interprets channels as signed16-bit values. Finite means, brightness consistency and the Q12 ratios are checked before processing. The model itself also rejects nonpositive, out-of-domain or duplicate adjacent locus points. Boundaries keep per-block products, optimizer products and the locus-distance arithmetic within their intended ranges.

The recovered connected filter uses **linear neighbour offsets**, including links across row boundaries. This checkpoint preserves and tests that behavior; it does not claim standard two-dimensional image connectivity. Radius is constant across this first policy, so its neighbour threshold is constant. Semantic, zone-override, exposure-dependent and spectral weighting are disabled. Candidate weighting is exposure-independent; no scene EV is fabricated. The context's otherwise-zero fields are working storage for these specific leaves, not a fully initialized firmware context.

All result gains and neutral values are cleared when a frame has no candidate. An accepted candidate has a separate diagnostic-only decision code. A failed final temperature interpretation has its own code and publishes no gains. Unsupported API input leaves the caller output unchanged. Caller objects must be complete and disjoint; handles are immutable, with scratch memory allocated separately for each call. Concurrent reads require externally synchronized destruction. Current allocations are suitable for integration research; device timing and memory optimization are unmeasured.

The caller must bind the grid and calibration to the same physical sensor/frame. The offline path uses the existing strict binder and still requires equal per-site normalization spans. The native candidate API does not independently prove those facts from a grid buffer. No candidate is authorized for rendering by this API, and source RAW/metadata are never modified.

## What the real capture showed

Both exported-black and dynamic-black interpretations of the saved12.6MP frame were regenerated from the original DNG and tested. At centre tint0, test radii128,256,512,1024 and2048 classify no blocks. Radius4096 produces a candidate while admitting nearly the entire image to the candidate calculation. The private sweep retains the exact counts, gains and CT/tint.

That broad acceptance does **not** establish correct white balance: it risks treating coloured subject matter as a neutral reference. Nor do the narrow rejections prove the actual illuminant is invalid. This is one uncontrolled indoor photograph without a known neutral target, and the policy centre/width are uncalibrated. The result is concrete evidence that the temperature model alone is insufficient to choose a shipping white-classification policy. The HAL result is neither an input nor a training target for this selection.

## Fresh checks

`PHONE_SCENE_RESULT.json` records exact source/input/binary identities:

- **192 cases**: two real black-level interpretations and30 synthetic RAW frames under six explicit test policies.
- **196,608 independent block comparisons**, covering admission reasons, nearest locus point, distance, classification, original weights, filtered weights and survival. A NumPy distance oracle, Python graph traversal and integer weighted-mean oracle independently check the native result.
- **101 diagnostic candidates and91 no-candidate results**. Published gains match the independent weighted mean exactly. Synthetic RAWs cover five illumination points, low/high exposure, saturation, below-black pixels, unequal green sites, small islands, mixed illuminants and signed-filter limits.
- **486 green-normalization checks** across the model loci, plus rejection of an unusable scene model with output-handle non-mutation.
- **16 native guards per probe**, output non-mutation, candidate→empty-frame clearing and deterministic replay.
- **15 exact24,636-byte result comparisons** against the shared-host result: five representative cases through optimized host, ASan/UBSan and Android API28 ARM64/QEMU. Cases include the real capture with and without a candidate, a neutral synthetic scene, mixed illumination and a rejected small group. All per-block traces and final outputs match.

The first compile required whitespace after a hexadecimal literal ending in`e`. The initial independent oracle used NumPy16-bit addition for the weight sum, which overflowed; that oracle was corrected to Python integer summation. The signed-gain fixture was also tightened to exercise the new signed-filter admission guard rather than an earlier RAW-ratio rejection. The final run is from the recorded source. LeakSanitizer remains unavailable due to executor `/proc` restrictions; address and undefined-behavior sanitizers remain enabled and fatal. No on-device image-quality, performance or full-controller parity claim is added here.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hasselblad_native_audit/phone_input_20261021/verify_phone_scene.py \
  --capture /private/IMG_20261020_062344.capture.json \
  --dng /private/IMG_20261020_062344.dng \
  --out /private/phone-scene-check --report /private/phone-scene-result.json \
  --ndk /tools/android-ndk-r27 --qemu /tools/qemu-aarch64-static \
  --firmware-root /private/extracted
```

The probe links owned sources only. Its Android replay uses the restored Bionic runtime; `libaaa.so` is not loaded. Original capture restoration remains `hasselblad.zip`, Library `libfile_20a4cdf4b5b8819198e741fda306316b`. Private bindings, candidate sweeps, grids, loci, result traces, executables and logs are saved as `Hasselblad_Phone_Scene_Candidate_Evidence_PRIVATE_20261021.zip`. Source and safe reports stay on the GitHub recovery branch.

## Next useful APK boundary

The candidate bridge is now a concrete new diagnostic capability for the next experimental APK. Restore Native1C capture-JSON/save-status behavior, expose the explicit test-policy identity and candidate/rejection provenance in diagnostics, and keep the existing photographic path until the phone policy is supported by controlled captures. A diagnostic build can gather that evidence before the entire automatic phone profile is complete. This follows the existing handoff's allowance for a bounded diagnostic upgrade; it is not a claim that this ordinary candidate is the full Hasselblad AWB decision.

The full controller still needs phone scene acceptance, ratio/exposure/spatial mappings and lifecycle/history initialization. Unavailable spectral data remain unavailable. Full photographic colour/HNCS validation remains separate. Preserve the application ID/signing identity, versionCode>27179, single-RAW/no-stacking behavior and JSON/DNG/JPEG outputs. Do not ship a Native1A downgrade. No APK or renderer change was made in this checkpoint.
