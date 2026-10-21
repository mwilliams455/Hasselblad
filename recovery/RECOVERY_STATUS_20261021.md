# AWB recovery reconstruction status — 2026-10-21

This branch is the durable reconstruction branch for the local Hasselblad Photon work that was lost while GitHub synchronization was failing.

## Verified preserved baseline

- Remote base commit: `929f523aa02ae5b224be39b9c36cce5975691a10`
- Base tree: `0ed5c57223c3e37c2e41140a23475c137345ddf1`
- User-supplied Native1A source archive SHA-256: `b8be2a7e121eb20e677dc573e129a98b6011526d5a29905acdea02158afd653f`
- Application ID: `com.mwilliams.hasselbladphoton`
- Restored app baseline: Native1A
- Last phone-validated build before recovery: Native1C `0.1-hb-native1c`, version code 27179
- Last recorded local AWB checkpoint before workspace loss: `aded05ef2f87402c051dd5746e6c58585bffe2b5`

The later local checkpoint is **not** present in the published Git history and is not represented here as recovered source. It must be reconstructed and revalidated.

## GitHub write-path status

On 2026-10-21 the previously failing GitHub write path was retested successfully:
blob creation, `create_tree`, commit creation and branch creation all completed and the written file was read back successfully. The test did not modify `main`.

From this point forward, newly reconstructed research checkpoints should be committed to this branch immediately after validation so they are not local-only.

## Recovered research/runtime inputs

The original X2D II 100C 1.3.16.2 firmware inputs were previously restored and verified against their recorded SHA-256 identities. Original firmware, vendor libraries, LUT payloads, APKs, and user photograph pixels must remain outside Git.

The reconstructed environment also freshly passed:
- 10,000 / 10,000 portable-vs-original WB recalibration comparisons
- 9 / 9 original routine cases
- 14 / 14 instruction coverage
- DNG writer fixtures and invalid-value guards
- clean Android build with both ARM64 and ARMv7 targets

These results establish the recovered small Q12 recalibration primitive and build environment only. They do not establish the complete scene AWB estimator or photographic HNCS renderer.

## Reconstruction order

1. Recreate the Native1C capture-evidence / JSON-storage checkpoint and metadata bridge.
2. Reconstruct the AWB research in bounded dependency order, rerunning original-vs-owned comparisons for every rebuilt numerical stage.
3. Sync each verified checkpoint to this branch immediately.
4. Keep `main` unchanged until the reconstructed chain is reviewed.
5. Do not include original firmware, extracted vendor libraries, user photos, private capture sidecars, generated APKs, or proprietary calibration/LUT payloads in Git.

Historical prose reports and old test counts are evidence of prior work, not substitutes for rerunning tests on reconstructed source.
