# Stage4 Photon RAW colour-basis / single-WB audit — 22 October 2026

## Question

Why does the original, untouched Bayer RAW scene classification move substantially when the original Camera2 lens-shading map is hypothetically applied? Where does the *existing* Photon renderer actually apply shading and white balance? This is a **source-contract audit**, not new native firmware parity or GPU byte-equivalence.

## Verified source flow on the current recovery branch

1. `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/processing/render/Parameters.java` reads Camera2's `STATISTICS_LENS_SHADING_CORRECTION_MAP` into `gainMap` and records `mapSize`; the Domain3 sidecar separately verified that original and effective maps have matching entries for the photographed frame.
2. `.../processing/opengl/postpipeline/PostPipeline.java`'s default pipeline registers `new Bayer2Float()` before demosaic and subsequent colour/tone stages. Different settings (including RGB layout) need separate validation.
3. `.../processing/opengl/postpipeline/Bayer2Float.java` uploads `mParameters.gainMap` to a `GL_LINEAR` texture and binds both `GainMap` and `mParameters.whitePoint` to `Bayer2Float/tofloat.glsl`, with explicit crop-relative map coordinates when present.
4. The shader declares `USEGAIN 1`. In the **ordinary Bayer (not RGBLAYOUT) branch**, it averages the two green gain-map channels, divides R/G/B gains by their channel mean (`gains.rgb /= mean(R,G,B)`), then on each colour-filter-array site computes `(normalized raw - black)/(1-black)/whitePoint.channel` and multiplies by the site-specific, normalised shading gain. This is where the existing Photon/Camera2 WB is applied to the scene-referred colour stream. Inpainted clipped regions have a separate branch; that alternative and GPU float/texture precision remain outside this static audit.
5. `.../processing/opengl/postpipeline/Initial.java` consumes `PostPipeline.GainMap` again for tone/white-point logic. This is **not evidence that colour-channel lens shading is multiplied twice**; any future numerical refactor needs a real render-stage trace.

## Consequences

- Stage4's earlier *full-gain-map* offline replay is a **sensitivity experiment**, not an exact emulation of Photon's shader. Its per-site absolute gain is not equivalent to Bayer2Float's *mean-normalised chromatic gain*. The normalized-gain CPU replay in the private evidence is explicitly labelled an approximate analogue, not verified GPU parity. Both confirm the importance of declaring the input shading basis.
- A future validated Hasselblad scene-neutral estimate must feed a **single** coherent RAW-to-linear WB application, replacing the appropriate existing neutral before the Bayer shader (or using a rigorously equivalent exclusive path), never multiplying WB a second time into already balanced pixels. Keep signed/headroom behaviour and the selected DNG colour transform consistent. This specifies an integration *boundary*, not permission to alter the installed renderer yet.
- Domain3 photographs still use the original HAL `neutral_used`; Stage4 generates no selected neutral at all. The completed firmware AWB reconstruction remains separate from phone calibration and subsequent HNCS CCM/tone/gamma/3D-LUT rendering.

## Reproduction

`neutral_observation/tests/verify_photon_color_boundary.py --repo <checkout> --out <report.json>` checks exact source contracts at the checked-out recovery commit without public sensor calibration or private image data. It must be re-run after modifying those upstream files; it is **not** an OpenGL/GPU execution test. The output contains only source hashes and pass/fail statements.

No camera pixel, shader or app source changes were made for this audit. Preserve the recovery branch; do not merge into `main` before the full phone automatic-profile and renderer integration is tested.
