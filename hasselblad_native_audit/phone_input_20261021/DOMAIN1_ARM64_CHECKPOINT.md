# Domain1 Android ARM64 link checkpoint — 21 October 2026

**Status: PASS (cross-compiled, not yet run on a phone).**

GitHub Actions run: [39671218983](https://github.com/mwilliams455/Hasselblad/actions/runs/39671218983)  
Source commit: `ba842be1a8a06a8e9e7522b445fdffd31c511318`  
Workflow: `.github/workflows/hb-phone-domain-arm64.yml`  

The recovery branch compiled `hb_phone_domain.c` together with the original
owned/reconstructed `hb_phone_temperature.c`, `hb_temperature.c`,
`hb_user_controls.c` and `hb_scene_optimizer.c`, targeting
`aarch64-linux-android28` (arm64-v8a) using pinned Android NDK `27.0.12077973`.
The library linked with no undefined references and contains the public
`hb_phone_domain_evaluate` entrypoint.

The resulting native ELF has three LOAD segments, each with **16,384-byte
alignment**. Build and ELF checks pass; source/binary identities appear in
`PHONE_DOMAIN_ANDROID_ARM64_RESULT.json`. The CI artifact
`hb-domain-android-arm64-link` contains only the library and report (7-day
retention), no private metadata or vendor firmware.

The previous real-leaf x86 host checks (O0, O2, synthetic profiles and private
capture replay) remain valid. **This checkpoint does not execute the module on
Android hardware**, does not install or build a new APK, does not implement an
Android JNI wire format or async cached domain reporting, and does not change
Photon photographic rendering. It does not select an automatic WB policy or
establish physical Kelvin/tint accuracy.

**Next release boundary:** Add a safe JNI wire/API for the Domain1 diagnostic;
bind it only to verified original Camera2 sensor matrices, report the explicit
grid and exclusion provenance, and run it on demand or once per bound physical
camera profile instead of in the synchronous shutter callback. Extend the
host JNI/Java replay and native failure guards before packaging a signed
same-application-ID upgrade with version code greater than 27183. Then validate
JSON and camera behavior on the phone. The complete automatic AWB phone profile
and HNCS saved-photo colour rendering remain separate follow-up projects.

Keep `main` unchanged, no forced radius/tint fitting, no silent temperature
point clipping, and never apply the candidate on top of Photon's existing WB.
