# Stage57: general colour consistency and a controlled comparison

The Stage56 phone report confirms automatic selection and display at 3550 K.
That is a device smoke result; it does not compare device pixels to a reference
or validate colour matching between physical cameras.

Stage57 tests the combined automatic LUT, highlight and finishing path. It finds
an open adaptation problem and adds **Automatic colour only** to the saved-DNG
comparison screen. The new view keeps the DNG matrix/WB, selected LUT, film and
native CPU finishing, while bypassing highlight reconstruction. The existing
automatic view is retained unchanged. No new profile or fitted parameters are
introduced; the Stage56 private `.hbc` remains compatible. Capture still uses
Photon. The two views are diagnostics, not a decision that either is a verified
Hasselblad match.

## Controlled experiment

Eight idealized camera encodings represent the same D50 colours. Six use
different neutral/channel scalings, and two add non-diagonal channel mixing.
ForwardMatrix and synthetic ColorMatrix metadata are constructed explicitly.
Each encoding is tested at eight metadata white points, from 2400 to 15000 K,
including the automatic LUT ceiling. These are **metadata/mathematical tests**,
not spectra, measured lamps, physical camera calibrations or new photographs.
The encodings' metadata are independently constructed at each white point;
they do not simulate one camera's spectral response across changing lights.

Each of the 64 cases contains three 9³ colour lattices with upper levels 0.12,
0.60 and 0.95, plus a 129-step neutral ramp: 2316 samples per case. Prepared
values are positive and below 65535 throughout. Both compared paths use the
same selected LUT and finishing. No brightness, colour, saturation or curve is
fitted. The current bridge's common prepared-RGB clipping ceiling is used; this
does not establish the correct physical sensor clipping model.

Maximum displayed channel spread between equivalent encodings, over all tested
metadata white points (0–255 scale):

| Target group | Without highlight reconstruction | With reconstruction |
| --- | ---: | ---: |
| Low range, up to 0.12 | 1 | 22 |
| Middle range, up to 0.60 | 1 | 58 |
| High range, up to 0.95 | 1 | 98 |
| Neutral ramp | 1 | 1 |

The 98-level extreme includes output-boundary colours. A separate control
requires both outputs to stay within 8..247, both LUT coordinate pairs strictly
inside the table, and both pre-film RGB triples strictly inside 0..65535. It
still finds a 40-level channel change. That example's maximum prepared input
is only about 0.111 of the encoding ceiling. Detailed derived colour samples
stay private; public receipts contain aggregate errors and reproducible indices.

This is representation dependence in the nonlinear highlight operation under
the current bridge assumptions. It is not evidence that Hasselblad's complete
pipeline has the same defect. Native source normalization, clipping provenance,
gain-map placement, RAW headroom and physical sensor calibration remain material
differences. Disabling reconstruction in a comparison does not recover lost
headroom or prove superior photographic colour.

## Independent and native checks

- Actual app Java/JNI processing executes all 64 cases. Metadata temperature
  agrees with the independent solve within 5e-11 K; camera matrices agree within
  9e-16. All selected LUT steps match.
- 889,344 colour-channel evaluations match the independent vectorized trace
  exactly. Highlight preparation, finishing C and independent output conversion
  are exact for these cases as well.
- Original ARM64 highlight and colour routines are replayed on nine sampled
  cases, including both extreme examples. They agree exactly with host JNI.
  Thus the finding is not an observed error in the reconstructed C routine.
- Existing Stage42/43/48/54/55/56 regressions and synthetic profile compatibility
  checks pass. CI uses synthetic profile data only.

## Retained photograph: execution check only

The same private DNG selects 3550 K. The existing automatic view remains
byte-identical to Stage56. The new view's 2,359,296 colour channels match the
independent trace; finishing and independently calculated output also match.
The on/off comparison changes 9,797 of 786,432 pixels by more than two display
levels in at least one channel, about 1.25%. Mean absolute channel change is
0.073/255; the maximum is 83/255. These are differences, not accuracy scores.
The photograph did not determine any coefficient or test threshold.

## Reference coverage and next work

The retained Stage44 evidence covers four Hasselblad RAW/camera-preview/JPEG
pairs, with reference-assisted exposure fitting. Those were not verified
Phocus exports, matched phone/Hasselblad scenes or blind cross-light validation.
The original cached arrays from that earlier workspace are unavailable here.
Two Library searches did not resolve additional references; this is a retrieval
limitation, not proof that no such files exist. The original Phocus APK was read
from the explicit local input and was not retrieved through Library.

Next, establish physical clipping/source normalization and preserve the needed
RAW headroom before promoting the highlight bridge to general capture use.
The new matched comparison permits testing that step independently across saved
DNGs. Controlled phone colour targets and known-settings reference renders are
still needed for photographic accuracy. No sensor-specific matrix is copied
onto phone samples, and no adjustment is fitted to the room photograph.

Hasselblad describes [HNCS](https://www.hasselblad.com/learn/hasselblad-natural-colour-solution/)
as covering colour, tone, contrast and colour-space transitions through the
workflow. That product description does not establish equivalence of this port.
Metadata construction follows the DNG conventions already cited in Stage56.

## Reproduce

```sh
python3 hasselblad_native_audit/phocus_generalisation_stage57/check_host57.py --work /tmp/hb57
```

For private audits, generate cases with `make_cases57.py`, run `Stage57Check`
with the private Stage56 profile, then `audit_generalisation57.py --help`.
`Stage57DngCheck` takes DNG, profile, output directory and previous Stage56
finished-RGB16 file; `audit_saved57.py` independently checks its new output.
Keep original files, profile bytes, hashes and derived arrays outside public git,
CI and APK assets. Public source and aggregate receipts are under this stage.

Build: `0.1-hb-compare57` / `27196`, same app identity and signing certificate,
both existing ABIs. Open Saved DNG colour, keep the Stage56 profile, and cycle
past Automatic colour to **Show automatic colour only**. The copied report must
show `automatic_colour_only`, `displayed_highlight_reconstruction: false`,
`displayed_native_finishing: true` and the selected LUT temperature.
