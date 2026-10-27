# Stage98 investigation: coloured-background coverage gap

The user reports that the Stage97 correction leaves visible purple around fine tree/sky boundaries. The newly supplied JPEG is resized and contains no EXIF. Its matching original DNG has not been supplied; no claim is made about the cause in that photograph. Neither the photo nor a photo-derived fixture is included here.

This checkpoint adds an investigation only. The application, renderer and latest APK remain Stage97 (27236), commit dabfdf0fae903891235a541c3096016cc5fbda13. Photo/Motion and the Hasselblad-only routing remain unchanged. There is no new APK.

## Confirmed limitation

Stage97 protects a pixel when either neutral-normalized chroma component anywhere in its 5x5 neighbourhood has magnitude >=0.16. This protects real colour, but also prevents correction when a legitimate coloured background itself exceeds that limit.

The diagnostic renders 120 synthetic dark-green lines against four backgrounds, using the actual Stage96 and Stage97 native paths. Cases span two neutral vectors, five angles and three line widths. All 60 blue/cyan cases have unchanged edge pixels: the colour guard blocks 100% of the pixels that otherwise have sufficient contrast and a nonzero median proposal. Grey and pale-blue cases receive limited correction. These are controlled source-camera colours, not inferred colours from the user's JPEG.

The previous regression suite demonstrated bounded changes and protected colour. Its red/green and blue/yellow comparisons remaining unchanged was not evidence that Stage97 would remove false colour around coloured backgrounds. Future acceptance must test actual error reduction there as well as regression limits.

Run `python3 hasselblad_native_audit/phocus_sky_stage98/probe98.py --work /tmp/hb-sky98` with GCC, NumPy and SciPy. The script builds the actual kernels, produces an aggregate summary and retains all synthetic case metrics in its work directory. The recorded run completed successfully. This is diagnostic evidence, not a new image-quality pass criterion.

## Next

Obtain the matching original DNG for the new tree/blue-sky JPEG. Trace prepared Bayer, interpolated RGB, post-noise RGB and final colour output on that same capture, and record Stage97 correction/gating coverage. Include both the earlier grey-sky RAW and this scene in candidate comparisons. Investigate a correction that estimates expected local scene colour rather than treating all substantial chroma as protected. Do not simply remove the colour guard: earlier stronger methods damaged faint-purple and red/green detail. Retain the 1,152 regression cases and add coloured-background false-colour reduction as an explicit acceptance requirement.
