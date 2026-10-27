# Stage97: bounded local chroma correction

The Stage96 neutral adapter reduces purple edges but leaves some isolated colour errors around fine dark detail. Stage97 adds a small local correction after the unchanged Stage96 reconstruction and before the existing camera-to-colour transform. This is a new source-camera adaptation, not a recovered Phocus primitive or evidence of proprietary pipeline equivalence. The recovered interpolation and noise kernels, Stage96 reference, profile, film curve, finishing and sharpening remain intact.

In DNG-neutral-normalized RGB, a 3×3 median proposes corrections to the two chroma coordinates `(R-G)/(R+2G+B+1)` and `(B-G)/(R+2G+B+1)`. Each correction is capped at 0.005 before quantization. A 5×5 neighbourhood colour guard and 3×3 brightness-contrast gate protect strong colour and flat areas. The correction preserves `(R+2G+B)/4` before RGB16 rounding. Zero corrections retain the original sample exactly. Any observed zero/saturated RGB sample in the neighbourhood prevents correction, as does a censored prepared Bayer sample (0 or 65535) within two pixels. Corrections that would introduce RGB16 clipping are rejected as a whole. These guards observe the prepared data; they are not an independent model of physical sensor saturation.

Tiles convert two extra real RGB pixels on every side, run the correction, then copy their centres. Internal boundaries never reflect or pad colours. Work remains banded and bounded with at most four workers. Invalid parameters or allocation failures take the existing capture-failure path. There is no alternate renderer fallback. Photo and Motion use this same path; Motion retains fresh timestamp-matched single-frame RAW and disabled legacy ZSL.

## Evidence and limits

The local suite covers 960 known-scene Bayer fixtures (four neutral vectors, five angles, four edge/line widths, two blur widths, six colour groups), plus 192 held-out cases with different white points, angles, noise and clipping. No case exceeds the defined material RGB regression threshold of `baseline RMSE * 1.05 + 0.0001`. This threshold permits small regressions; it is not a claim that all errors improve. Mean neutral-edge chroma RMSE falls by about 9.3%. Red/green and blue/yellow fixtures remain identical. Strong-purple average chroma error rises slightly (about 0.16%); pale-purple and dark-purple averages improve. The largest added RGB RMSE is approximately 0.000131.

Native output agrees with an independent NumPy/SciPy implementation within one RGB16 code, including assembled band boundaries. Tests cover luminance rounding bounds, clipping guards, flat-neutral identity, worker determinism, tail anchoring, invalid-call output preservation, JNI and cancellation. Address/undefined-behaviour sanitizers exercise the adapter. The existing capture suite retains 110 Photo/Motion/failure cases and 1,490 checks. CI enables LeakSanitizer as well.

The private supplied RAW was replayed through the automatic Curve1 colour pipeline with sharpening. The change is modest; it is not a complete removal of the visible pink. Photo diagnostics are not ground-truth image-quality scores. No private photo, profile, native executable or derived image fixture is distributed in this repository or APK.

Stronger alternatives were rejected: a larger local filter damaged faint purple detail; the original native positive-strength ColorNoise path greatly increased red/green and strong-purple errors; a luminance-preserving variant of the Stage96 adapter also regressed colour. Those experiments do not establish an optical cause for the remaining fringe. Stage97 does not change preview math or exposure selection and does not establish preview/output parity.

## Run and phone acceptance

Run `python3 hasselblad_native_audit/phocus_edges_stage97/check97.py --work /tmp/hb97-tests` with GCC, Java17, NumPy and SciPy. JNI headers come from `JAVA_HOME/include` or `--jni`. If the host prevents LeakSanitizer from inspecting `/proc`, local checks may use `ASAN_OPTIONS=detect_leaks=0`; retain the CI leak check.

Install `0.1-hb-edges97` (27236) over Stage96 without clearing app data. Existing profiles and preferences are retained. Compare fresh RAW+JPEG captures of branches/sky and real purple, red and blue detail in Photo and Motion at the same viewing scale. A successful build and host replay do not substitute for phone validation. High-ISO image quality, broad scene coverage and complete fringe removal remain unconfirmed.
