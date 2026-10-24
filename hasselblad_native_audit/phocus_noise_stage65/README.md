# Stage65 — bounded independent `ColorNoise` CPU reconstruction

**Status: HOST-VALIDATED CANDIDATE; NO DIRECT ORIGINAL-CPU OR DEVICE PARITY.**

Stage65 extends the previously verified Stage63 ten-component gradient pipeline
and the Stage64 **candidate** `DirectionalColorCorrectionYCC`. It supplies a
scene-agnostic C11 implementation of the two bounded original `ColorNoise`
branches, with explicit unsupported-route reporting. It is not a new APK,
complete independent demosaic, or physical colour-fidelity validation.

## Native static evidence and scope

Private analysis of the locally supplied Phocus 2 ARM64 CPU implementation
identified three distinct pieces of `ColorNoise` behavior:

1. **Flag bit 5:** for width and height at least 17, convert an RGB16 interior
   region (8-pixel margin) into a uint16 luminance and two signed chroma planes.
   Inputs are `R,G,B` at the current pixel. Luminance is `(R+2G+B)>>2`; signed
   chroma uses `(R-G)*32768/(R+2G+B+1)` and the analogous B-G quotient with
   signed division **toward zero**. The subsequent 3×3 eight-neighbour min/max
   clamp updates the luminance buffer **in scan order**. No generic in-place
   neighbourhood smoothing or alternate clamp ordering is assumed.
2. **Flag bit 6 with nonoptimized scalar route:** process rows 1 through
   height−2 using the Stage61-equivalent integer 1–2–1 smoothing and signed
   median-of-row-medians for both chroma planes. On the 12-pixel-margin interior,
   a zero packed direction mask copies luminance and zeroes the auxiliary plane;
   a nonzero mask calls the Stage64 independent directional-YCC candidate.
   A signed-16-bit-wrapped absolute-magnitude comparison selects the local
   candidate or median chroma for the final two output planes. The original
   routine uses different storage for the fourth YCC helper output and its
   third output; both are preserved in the adapter.
3. **Positive `strength` while flag bit 6 is active and optimized-view is off:**
   a separate path calls the still-unported `getYErrorMapShort` and
   `ColorFilter2Short`. Stage65 returns **-2 without mutating buffers** instead
   of pretending that the simpler code represents this path. Optimized-view
   dispatch is also not reconstructed; the audited bypass is preserved.

This is an independent implementation inferred from static ARM64 instructions,
not a copy of any original executable bytes. The original body, intermediate
CFA alignment scheduler, graph parameter constructor, full-frame boundaries,
and Android integration are not present in public Stage65 source.

## Independent source

- `noise65.h` / `noise65.c`: explicit arrays, width/height/stride/flags,
  signed arithmetic and side-effect/unsupported-route rules. The support
  contract requires separate valid buffers and no edge extension.
- `portable65.py`: build host C11 library with Stage64 `ycc64.c`, without
  loading any original vendor code.
- `test_noise65.c`: standalone source-focused C regression including 8/12px
  margins, zero dimensions, neutral, impulse and unsupported-route guards.
- `test_host65.py`: a separate Python reference for no-mask paths, comparing
  entire buffer storage (including untouched margins and row padding).
- `audit_native65.py`: **prepared, not executed** direct original ARM64
  `ColorNoise` versus independent C full-buffer parity runner. It exercises
  bounded flag combinations, sizes, inputs, masks and memory guards.
- `audit_graph_flags65.py`: **prepared, not executed** native graph-observer
  to identify which `ColorNoise` configurations are exercised by the existing
  graph-captured Stage63 fixture. No private photos or calibration values
  are written into its planned public aggregate receipt.

The Stage64 `DirectionalColorCorrectionYCC` remains a dependency for nonzero
mask correction. Until it itself passes original CPU checks, independently
matching the whole Stage65 composition against the Stage64 candidate/model is
**not** proof of native Phocus parity.

## Actual host tests performed

GCC C11 `-O2 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off`;
AddressSanitizer and UndefinedBehaviorSanitizer enabled. C standalone
self-test passed. Python compiled without errors.

The independent Python reference suite completed **384 synthetic cases**:
zero/flat/full/random codes, dimensions 1–48, nontrivial strides, bypass/flags
and zero-direction paths. Every included output buffer, input and unwritten
slot matched C across **4,315,584 storage elements**, zero differences. Of
these, **64 cases** deliberately received unsupported `-2` for positive noise
strength without changing any buffer. These storage elements are **not** extra
photograph pixels and the counts cannot be added as independent RGB outputs.

A private read-only bounded evaluator of the original Stage64 ARM64 *instruction
listing* was composed with Stage65 for **320 nonzero-mask cases** / **1,280
observed output codes**, including all **256 low direction masks** and candidate
selection comparisons. All matched; 122 tests selected the median candidate.
This is a private **instruction-model** cross-check and does **not** execute
the original ARM64 CPU function. Original disassembly and model code remain
outside GitHub. No DNG pixels, source hashes or calibration matrices were
published.

## Native/Android gates still required

The local environment has the supplied private Phocus APK and extracted native
library, but lacks the previous Stage60–63 Unicorn, Capstone and pyelftools
runtime. Neither `audit_native65.py` nor `audit_graph_flags65.py` could be run.
Stage64 direct YCC runner and its eleven-kernel connected substitution are
also **still pending**; do not promote Stage64 or Stage65 to native-verified
status from this host research checkpoint.

When a private host with the previous emulator stack is available, run:

```sh
python3 hasselblad_native_audit/phocus_colour_stage64/audit_ycc64.py \
  --apk /private/local_phocus.apk --work /private/stage64-native \
  --safe-receipt /private/stage64-native.json --sanitize
python3 hasselblad_native_audit/phocus_colour_stage64/audit_integration64.py \
  --apk /private/local_phocus.apk --dng /private/input.dng \
  --work /private/stage64-substitution \
  --safe-receipt /private/stage64-integration.json --sanitize
python3 hasselblad_native_audit/phocus_noise_stage65/audit_native65.py \
  --apk /private/local_phocus.apk --work /private/stage65-native \
  --safe-receipt /private/stage65-native.json --sanitize
python3 hasselblad_native_audit/phocus_noise_stage65/audit_graph_flags65.py \
  --apk /private/local_phocus.apk --work /private/stage65-graph \
  --safe-receipt /private/stage65-graph.json --sanitize
```

**Abort on any native mismatch**, unexpected register/memory alias, out-of-range
padding, missing helper call or unsupported graph flags. In particular, retain
the original `ColorNoise` bit-5 intermediate code ordering and investigate any
reference output divergence; do not force a photographic look fit to hide it.

Only after the graph's exact feature flags and ColorNoise branch are validated
should the full **`InterpolateRGB` pixel-loop orchestration** be independently
ported and tested, with original remaining `getYErrorMapShort`/
`ColorFilter2Short` paths either supported or excluded under a justified
fixed-configuration contract. Then prove a full demosaic with no original
pixel-code operations, host-to-JNI parity, exported-device pixels, and
comparison against physically matched Hasselblad references before an APK
renderer change.

## Privacy and baseline

The private original APK, photographs, source disassembly, calibration and
private LUTs are not in GitHub or distributed output. The current Stage58
phone build and experimental saved-DNG view are unchanged; ordinary captures
still use Photon. Target remains scene-agnostic, approximately 12MP SDR,
single-frame capture, all phones/lenses where support is justified; no HDR,
stacking or video and no tungsten-room look fitting.
