# Stage95: restore Motion with Hasselblad rendering

The mode picker now exposes Photo and Motion. Both use the same single-frame Hasselblad RAW-to-JPEG renderer, selected curve and sharpening. Startup and preference reads/writes retain either supported mode; unsupported old mode values normalize to Photo. The picker maps its two positions explicitly to the existing CameraMode enum ordinals, so a saved Motion selection is not confused with a UI index. JPEG colour/exposure preview is eligible in both modes.

Motion retains the existing shorter-shutter exposure selection in IsoExpoSelector, including its existing sensor, manual-exposure and stability behavior. No exposure or pixel-processing algorithm was changed. One RAW frame, no stacking/HDR and standard advertised RAW sizes remain enforced. Stage94's no-Photon-fallback capture handler, error reporting, cleanup and save behavior are unchanged.

## Fresh RAW rather than the legacy ZSL ring

The inherited Motion/ZSL ring attaches the latest preview CaptureResult to buffered RAW images and does not populate the full original sensor/source evidence required by Hasselblad. Enabling that path would violate timestamp pairing or reject captures. In this build Motion uses the existing fresh still-RAW request path, with the capture's own matched result and source surface. This restores Motion's faster-shutter use case; it does not claim zero-shutter-lag buffered capture. A future buffered implementation must retain and match per-frame physical metadata and RAW layout before enabling it.

## Verification

`python3 hasselblad_native_audit/phocus_motion_stage95/check95.py --work /tmp/hb95-tests`

The harness compiles the production mode enum, supported-mode mapping, startup policy, capture router, handler and output-mode logic. It retains all 62 Stage94 routing/failure scenarios and adds Motion JPEG/RAW+JPEG/RAW success, pre-save/native/encoding/publication failures, invalid modes/inputs, cancellation, preference persistence and picker mapping. Android I/O/native rendering are test doubles; these are orchestration tests, not a phone capture or image-quality claim.

`python3 hasselblad_native_audit/phocus_motion_stage95/pins95.py`

Pins bound the capture-controller edit to disabling the incompatible legacy ZSL ring, and the preview edit to its mode eligibility gate. Exposure selection, preview pixel math, native rendering and DNG transport remain unchanged from Stage94. CI verifies version/signing, both ARM ABIs, ELF 16 KB alignment and unchanged shader assets.

## Phone acceptance

Install over Stage94. Select Motion beside Photo, take a fresh JPEG or RAW+JPEG, and confirm the last-capture status identifies Hasselblad. Switch between Photo and Motion, reopen the app and verify the chosen mode persists. Confirm live selected-curve preview works in both modes. Automatic Motion capture should favor shorter exposure times than Photo for a comparable handheld scene, subject to sensor and manual settings. The overall preview/output match still requires device validation.
