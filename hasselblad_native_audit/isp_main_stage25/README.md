# Stage 25 — MAIN CCM descriptor-to-driver contract join

**22 October 2026 · X2D II 100C firmware 1.3.16.2**

Stage 25 continues the firmware-first colour reconstruction without changing the Photon saved-photo renderer. It does not guess a Hasselblad look and does not promote the six stored MAIN CCM values into an assumed 2×3 or 3×3 RGB equation.

Stage 17 proved the original MAIN CCM profile preparation and its 16 × 6 signed register layout. A separate bounded driver audit recovered the destination ranges written by ccm_set_ig0_config. This stage joins every original DIQ_iq_main_ccm parameter getter to its exact librcam register descriptor and then to those already-proven driver destination families.

The retained result can name which original features occupy the 3-, 5-, 6-, 9-, 16-, 25- and 96-register ranges around lmtx_fw. It contains no vendor coefficient values, instruction bytes, photographs or firmware payloads.

The remaining hard gate is unchanged: the six-coefficient pixel equation, Q scale, channel order, group selector, clipping, rounding and MAIN gamma/LUT handoff need a MAIN-specific hardware specification or a controlled before/after ISP pixel oracle. A neutral-preserving constrained 3×3 interpretation remains only a hypothesis.

Synthetic test:

    python3 hasselblad_native_audit/isp_main_stage25/inspect_main_ccm_contract25.py --self-test

Exact-source run:

    python3 hasselblad_native_audit/isp_main_stage25/inspect_main_ccm_contract25.py \
      --repo-root . \
      --firmware-root hasselblad_native_audit/firmware/extracted \
      --output /tmp/STAGE25_MAIN_CCM_CONTRACT.json

Production boundary: main is unchanged; no APK or Android camera code changes here; Stage24 remains a neutral/colourimetric reference rather than HNCS; Stage21 remains a hypothetical MAIN LUT sampler; Stage8 build 27186 remains the latest phone-tested APK.
