# Native1C candidate + AWB research reconstruction checkpoint — 2026-10-21

## Evidence classification

This file reports **fresh host verification** separately from **historical conversation-recorded AWB results** and **untested reconstruction candidates**.

### Freshly verified in this session
- The preserved Native1A source ZIP is accessible and extracted (SHA-256 `b8be2a7e121eb20e677dc573e129a98b6011526d5a29905acdea02158afd653f`).
- The previously saved Native1C private capture DNG/JSON matched the pinned original capture identities. These private inputs are NOT committed.
- Recreated unchanged Photon metadata bridge: **25/25** replay checks passed, including **57 original input scalars**, **18 matrix-output scalars**, interpolation weight `0.3396311136626453`, and 10 iterations.
- Independent metadata review: **12/12** checks passed (including Java synthetic checks, optimized + ASan/UBSan C checks).
- A candidate Java source patch restoring Native1C-style capture evidence, physical-camera/RAW identity, SAF JSON storage and in-session save-status UI passed **19/19** structural/host-Java/XML checks and a separate **25/25** source checklist. **These are not Android compilation or device tests**.
- Portable Q12 recalibration arithmetic 10,000/10,000 valid and 4 negative input cases passed; this session did NOT run the original ARM64 vendor routine.
- A small AWB outer-completion model based on archived offsets/statuses passed **2,562/2,562** synthetic assertions in optimized and ASan/UBSan builds. Original ARM64 comparison is NOT performed; reference-request ordering remains to be confirmed.

### Reconstructed but not yet revalidated
The complete AWB research conclusions survive in `CONVERSATION_AWB_RESEARCH_LEDGER.md` and the mega handoff. These preserve the 920,560-byte state, 1,000-byte REAWB handle, E2 32x32 statistics, weighting, filtering, optimization, history, atmosphere, CT/tint, output, passive REAWB, and outer recovery. The unpublished original source commit `aded05ef2f87402c051dd5746e6c58585bffe2b5` is absent. Historical seven-frame full-state comparisons are **NOT** new results of this checkpoint.

Historical last supported normal route: ordinary illumination 0, scene 3 sole eligible. No-eligible scene inner status 40 and a post failure 151 can each be followed by confirmed-result restoration and outer return 0. Therefore selected-neutral freshness/provenance must be separate from the final success flag. Missing spectral input need not block the tested ordinary route. Active linked-storage REAWB not recovered.

## Native1C APK boundary
Keep installed `0.1-hb-native1c`, version code **27179**, unchanged. The source patch is **not a rebuilt APK**; it is a host-checked candidate that has not been compiled with Android SDK or tested on the device. The eventual APK must use `com.mwilliams.hasselbladphoton`, same signer, version code **greater than 27179**, and preserve DNG/JPEG/JSON behavior. Do not replace the installed build with Native1A.

## Next requirements, in order
1. Rebuild Android toolchain; compile, correct, and device-validate the candidate capture JSON/SAF patch, including matched RAW/DNG/JPEG/hash, stream provenance and UI status.
2. Reconstruct the whole supported firmware AWB chain from the saved research spec and rerun same-execution original ARM64 versus owned code comparisons (optimized + sanitizers). Sync each checked stage to THIS branch.
3. **Genuinely new AWB research:** general ordinary scene-controller loop (more than scene 3), earlier frame preparation/lifecycle; active REAWB and extra spectral modes only when required.
4. Calibrate Camera2 RAW/statistics for each physical phone sensor without copying X2D IMX861 sensor calibration. Produce freshness-labelled neutral beside unchanged HAL metadata.
5. Prove signed/unclipped headroom RAW-to-linear/demosaic input and apply coherent WB once. Existing Photon colour matrix already includes WB; do not double-correct.
6. Resolve saved-photo MAIN HNCS CCM/gamma/3D LUT per-pixel equation, numerical domain, interpolation and operation order; display LUT sampler is not proof.
7. Do offline identical-RAW tests and then phone preview/still, lenses, tungsten/daylight, performance and failure validation.

The fastest useful next debug APK can expose **diagnostic-only** recovered AWB neutral/provenance before full HNCS, once relevant AWB original verification and Android stability are established.

**Privacy:** no original proprietary firmware/vendor libraries or calibration payloads, no private photo pixels/full sidecars, no generated APKs committed. **Do not advance `main` until the chain is reviewable.**

**Artifact:** local, user-deliverable `Hasselblad_Native1C_Reconstruction_and_AWB_Recovery_20261021.zip` contains patch, source validation and host-only AWB model; the private inputs and vendor runtime are intentionally excluded. Local artifacts cannot be claimed uploaded to GitHub until separately synced and read back.
