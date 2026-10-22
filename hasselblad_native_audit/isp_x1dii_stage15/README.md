# Stage 15 — X1D II 50C v1.0.0 firmware comparison for the X2D II MAIN CCM pixel equation

**Research purpose:** Use the public [older X1D II firmware dump](https://github.com/derrickyau9/Hasselblad_X1D_II_FirmwareDump) as an independent architectural and arithmetic lead. **The X2D II 100C 1.3.16.2 CCM pixel equation is not yet proved.** The newer phone renderer must remain Photon-only.

## Input identities and architecture

- Public older firmware commit: `f39ac51d6b92c19f9b34e35d5f32f985a1c1cbe5`, extracted `_X1D_II_50C_v1_0_0.cim.extracted/system.img`.
- The older operating system declares Android **6.0 / SDK 23**, ARM **32-bit** `armeabi-v7a`, and DJI **Eagle EC1704**; original `etc/VERSION` is `1.0.0`.
- The newer X2D II audit uses firmware `1.3.16.2`, Android 9 ARM **64-bit**, the verified `librcam.so` X2D II SHA256 `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`.
- The older model's `dji_rcam.conf` names `sensor_name = X1DM2`, `config_name = x1dm2`.
- X1D II `imx161f_ec1704.sp` declares separate main and HDR still-processing graph nodes. JPEG and RAW playback main paths include PFR, HISO and XIDIRI nodes. *Declared nodes are not proof of activation*; `dji_camera.conf` sets `pfr:ceva` and `xidiri:ceva` `process_switch=disable`, while `hiso:ceva` is `auto`.

## Early directly inspected executable metadata

- The **actual** older `libdcam_pp.so` ARM32 `.dynsym` exports multiple HDR/HISO/PFR/DSP operations and sky-colour-inpaint helpers. Its named `P_color_LUT` operations belong to that sky inpaint path, **not an established photographic CCM pixel transform**.
- The **actual** older `libdcam_fcali.so` exports AWB calibration, `fcali_load_awb`, and scene/sensor statistics operations. Its embedded strings mention *golden rgain/bgain*, calibrated R/B gain, and `AWB_CALIB_UNIT_STAT_RG/BG`. This is a potential separate Stage7 calibration lead, **not a colour-matrix equation**.
- The **actual** older `libmod_dji.so` exports named object descriptors `imx378_iq_ccm_settings`, `imx378_iq_gamma_settings`, and `imx378_iq_apost_lut3d_settings`. Those are IMX378 *tuning metadata leads*, not evidence for the X1DM2 sensor or X2DII pixel formulas.

## Controlled CI investigation

`inspect_x1dii_isp.py` downloads eight target ARM32 libraries/driver files plus exact-hash text configuration into an ephemeral GitHub Actions process, using **Git blob SHA-1 plus exact size pins** recorded from the public upstream repository. The analyser uses pyelftools and Capstone on inert data; no old vendor binaries are run, no extracted firmware is committed. For each relevant ELF it publishes only structural evidence: ELF class/architecture, selected *names* and address/size data, rodata source path references, filtered diagnostic strings and mnemonic class counts from identified CCM functions. It does **not** publish proprietary code, data tables, photographs or full disassembly.

A known mismatch is deliberate: the older X1D II is ARM32 and the X2D II is ARM64. Even a shared symbol name cannot establish equivalent CCM pixel arithmetic. The proof requires a matching original MAIN-connected pixel operation with input/output values, channel order, fixed-point scale, clipping and relevant stage composition.

### Reproduction

```
python hasselblad_native_audit/isp_x1dii_stage15/inspect_x1dii_isp.py --self-test
python hasselblad_native_audit/isp_x1dii_stage15/inspect_x1dii_isp.py \
  --output /private/STAGE15_X1DII_ELF_AUDIT.json
```

The networked second command is intended for the ephemeral GitHub Actions runner and requires exact pinned public files. Do not run vendor executables or build the old firmware for a phone.

## Next proof gate

1. Identify where X1D II exports its X1DM2-specific CCM coefficient **descriptors**, versus any actual pixel math; compare the older register/colour path with the independently proven X2D II 16-by-6 CCM register layout.
2. If a candidate pixel-math routine is found, audit its original ARM32 instruction effects on **synthetic** bounded inputs, then compare its numeric model with the original X2D II pathway. Any difference is valuable and must not be silently hidden.
3. Maintain strict distinction between the Stage14 synthetic software-ISP *display LUT* hypothesis and the actual photographic MAIN CCM/GAMMA/LUT processing. **No new APK or photographic colour enablement from this audit alone.**
