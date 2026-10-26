# Stage96: source-neutral chroma correction

Fine branches against a bright background can acquire purple colour in the Stage95 output. The recovered ColorNoise stage computes chroma relative to equal R/G/B values and selects corrections toward zero chroma. Source-camera RAW white is generally not equal R/G/B. Stage96 adapts that stage to the DNG AsShotNeutral before passing its result to the existing source-camera colour transform.

The adapter runs the unchanged Phocus interpolation on unchanged prepared Bayer data. It then scales the three RGB planes by `min(1,nR,nB) / [nR,1,nB]`, runs the unchanged ColorNoise/YCC kernels, and restores camera RGB before the existing colour, curve, finishing and sharpening path. All input factors are at most one; balancing cannot clip input highlights. Restored RGB uses the existing unsigned 16-bit output domain with rounding and saturation. Neutral ratios are validated as finite, positive and within 1/16..16; unsupported metadata rejects rendering through the existing capture failure path. There is no alternate renderer fallback.

This is a source-camera adaptation, **not** a newly recovered Phocus kernel or a claim of equivalence to the proprietary native input graph. Stage74/77 references remain intact. The older numbered diagnostic activities retain their reference implementations. Normal capture and the automatic saved-DNG renderer use Stage96. Capture reports identify `phocus-chroma96` and include the neutral needed to reproduce their diagnostic samples; old Stage74-only comparators cannot validate those adapted samples without this metadata.

## Evidence and limits

Two privately supplied RAWs were replayed through the existing automatic Curve1 colour pipeline. Neither had saturated sensor samples or gain-map clipping. The candidate visibly reduced purple edge colour in both. A simple magenta-like pixel count in a fixed upper-image region fell by approximately 42% and 57%. This is a diagnostic signal, not scene ground truth or a general image-quality score. No private photo, profile, device identifier or photo-derived fixture is in this repository or APK.

The reproducible synthetic suite uses 180 Bayer edge scenes: four neutral vectors, five angles, three blur widths and neutral/red-green/blue-yellow edges. Mean chroma error changes approximately as follows:

| Edge group | Stage95 | Stage96 | RGB RMSE regressions (>5% + 0.0001) |
| --- | ---: | ---: | ---: |
| Neutral | 0.007001 | 0.003906 | 0/60 |
| Red/green | 0.029417 | 0.027336 | 7/60 |
| Blue/yellow | 0.018928 | 0.017068 | 2/60 |

Errors are measured after neutral normalization in linear source RGB. Some colour-edge cases trade RGB accuracy for chroma suppression; the largest added RGB RMSE in this suite is about 0.00334. These results justify a focused test build, not a claim that every fringe is fixed. Wider validation, including clipped highlights, high ISO and fine coloured detail, remains necessary. M9-style MHC, M10R AMaZE and balancing the whole Phocus demosaic were tested as alternatives; they did not justify replacing the existing interpolation.

## Checks

Run `python3 hasselblad_native_audit/phocus_chroma_stage96/check96.py --work /tmp/hb96-tests` with GCC, Java17, NumPy and SciPy. The script obtains JNI includes from JAVA_HOME or `--jni`. Address/undefined-behaviour sanitizers cover the actual native adapter; CI also enables leak detection. In a sandbox that prevents LeakSanitizer from inspecting `/proc`, use `ASAN_OPTIONS=detect_leaks=0` locally and retain the CI leak check.

Checks include exact Stage77 parity for unity neutral, 1-vs-4-worker agreement, tails and partial bands, input immutability, unchanged output on rejected calls, metadata/capacity bounds, actual Java/JNI calls and cancellation, 20 flat-neutral cases, and the synthetic edge matrix. The prior Photo/Motion routing, preference and failure checks are retained with Android I/O/native rendering test doubles. The pins script bounds the application changes to this adapter and diagnostic metadata. CI builds both ARM ABIs, verifies the existing signing identity, 16KB ELF alignment, version, absence of private profiles/RAWs, and unchanged preview/reference assets.

## Phone acceptance

Install `0.1-hb-chroma96` (27235) over Stage95 without clearing app data. The imported profile, curve, sharpening and Photo/Motion settings are retained. Take a fresh RAW+JPEG of fine branches against sky, then a scene with real purple/red/blue detail. Check both modes and compare at the same scale. The build does not change exposure selection or preview math. Some optical/sensor fringe may remain; an APK build and host tests do not establish phone image quality or preview/output matching.
