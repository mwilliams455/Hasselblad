# Stage69 — real-kernel scalar host composition candidate

This stage connects the independently implemented Stage61/62/63/67/68
components through Stage66's bounded scalar `InterpolateRGB` scheduler and
plane-ownership adapter. The `HB69Callbacks` invoke actual C kernels: there
are **no mock interpolation functions in the production adapter**. The host
comparison `test_integrated69.c` independently expresses the *ordering* using
the **same** underlying C kernels, so host parity checks composition only,
not independent mathematical or original-CPU equivalence.

This source was prepared on the Stage68 checkpoint `40a7308d21fe280f7dd464a3027d36968a9fac69`.
It does not require a camera, Phocus APK, private DNG, vendor libraries, or
calibration files to compile and run synthetic fixtures.

## Supported contract

- Aligned RGGB working frame only, dimensions each multiple of 8 and >=24,
  `stride >= width`; original alignment, CFA phase discovery and frame-edge
  extension remain unsupported. Flag word `0xffff` only.
- Caller supplies 11 mutually disjoint full-frame arrays: raw R/G/B/mask,
  smoothed RAW, signed edge, horizontal/vertical scales, midgreen scale and
  midgreen codes. No allocation or staging inside the adapter. Temporary
  arrays and output planes must be appropriately initialized by the caller.
- Caller owns the scale contrast threshold and the first/second gradient
  threshold floors. These are **explicit inputs**, not scene-fitted values.
- Preparation smooths original RAW rows, creates the signed-edge map from the
  smoothed rows, calculates scale maps and midgreen codes, and then copies
  original RAW into the working green plane.
- Stage68 colour-site directional gradients (six-term diagonals) feed the
  Stage63 green estimator at R/B CFA sites; Stage67 green-site RAW gradients
  (four-term diagonals) feed the Stage61 direction-mask selector at G sites.
- The two Stage62 missing-colour helpers use output RGB planes and the
  intermediate green plane. Masks equal to zero preserve Stage66's explicit
  bypass, writing zero instead of invoking these helpers.
- Stage66 margins of 4, 6 and 8 pixels and original per-pass CFA ownership
  are retained. Sources and scratch buffers must not overlap, and the adapter
  validates these before any writes. On an error after starting preparation,
  previously written outputs may remain changed.

**Known open questions:** Source buffers and colour/noise flags still need
original-CPU execution and actual graph-dispatch verification. The adapter
uses Stage61 `smooth/edge` and `scale/midgreen` preparation contracts but the
full original memory lifecycle, output clipping/storage semantics beyond the
bounded helper contracts, pad/crop policy, metadata import and non-scalar
path remain unverified. Retained signed threshold floor values must be read
from the original native context before meaningful CPU parity comparisons.

Stage64/65 colour-noise functions are *not* invoked here. Positive-strength
noise handling is outside scope. Output here is a bounded host RGB16 plane
candidate, before colour LUT, finishing, film, gamut conversion or display.
No original executable body or photographic pixels are bundled.

## Tests

`test_integrated69.c` runs 16 deterministic synthetic combinations:
24x24, 32x40, 64x64, 80x88 frames, including padded strides, for constant,
structured-gradient, seeded-random and extreme-edge inputs. It independently
repeats every phase using the same underlying Stage61/62/63/67/68 kernels,
compares **all 11 complete plane/storage arrays**, tests source immutability,
guards, unsupported flag rejection, scratch overlap and invalid thresholds.

This tests *composed host implementation*, not the vendor algorithm. New
GitHub Actions workflow `hasselblad-stage69-host.yml` builds the **canonical
GitHub source tree** with AddressSanitizer + UBSan. Do not mark host CI as
passing unless the workflow actually finishes successfully.

This container may not have the Stage61/62/63 full source tree mounted; it can
compile adapter and test separately and use the committed workflow for an
end-to-end synthetic source build. The original CPU Unicorn/Capstone/
pyelftools runtime is not available in this environment, and no original
executable, native instruction trace or private DNG has been exported.

## Next gates

1. Complete the Stage69 synthetic CI run, fix any ABI/math or wiring mismatch.
2. Run Stages64–68 private native validation scripts using the supplied original
   APK in a runtime with the required emulator dependencies.
3. Compare `hb_interpolate69` final interior RGB16 against the original scalar
   CPU under **measured** graph flags and supported geometry. Do not call the
   complete demosaic portable until all remaining native pixel operations and
   memory/edge contracts are resolved.
4. Independently validate bounded Stage65 ColorNoise and Stage64 directional YCC
   before integrating them; preserve the Stage58 device baseline, no new APK.

The target is general Hasselblad rendering fidelity, not a tungsten-scene fit.
Other sensors and CFA phases need their own input-domain adaptation checks.
