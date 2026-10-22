# Stage 27 — MAIN CCM invariants for exact X2D II firmware (research only)

**22 October 2026 · Hasselblad X2D II 100C firmware 1.3.16.2**

## Why this stage exists

Stage17 recovered the original CCT/high-ISO Q8 interpolation and Stage25 joined 27 MAIN CCM parameter names to the actual Eagle2 driver register families. The exact static global still `lmtx_fw` table contains **eight 96-value source profiles**, grouped as four CCT knots times two high-ISO banks. Each profile contains **16 groups of six signed values**. Stage17 previously observed that all 16 groups were identical in each of those eight profiles, and that the two high-ISO banks were identical for each of the four temperature knots.

Stage27 turns those observations into a **precise restricted invariant**, with adversarial synthetic controls and an independent C-vs-Python Q8 interpolation test against the exact hash-pinned firmware table. No vendor coefficients or original firmware code are committed.

## Formal result, conditional on successful original-firmware CI

The original-verified `hb_ccm_prepare` interpolates the same component index independently across source CCT profiles and high-ISO banks. Therefore, if the 16 source groups are identical at every CCT knot, interpolation preserves equality for **all** CCTs (including intermediate and clamped endpoints). If high-ISO banks have identical source values at each knot, any legal Q8 high-ISO bank weight produces the same 96 prepared values.

For **this exact static global still CCM table**, a selector restricted to one of the 16 groups cannot affect the **chosen six coefficients**, and a high-ISO bank-rate change cannot affect that table's prepared coefficients. This holds without guessing *which* group is selected.

This is not a proof that the entire CCM pixel result is region-independent under all runtime circumstances. Dynamic frame-level overrides, distinct still/video tuning tables or different firmware may invalidate the simplification. No hardware pixel arithmetic, region selection logic, coefficient Q scale, RGB geometry or clipping is recovered here.

## Safety/evidence boundaries

The test fails closed unless the official IQ configuration, known CCM table SHA, parser SHA, original parameter schema, axis and table shape all match previous checked evidence. It compares Stage17's portable **C** arithmetic against independent Python interpolation across 141 CCTs × 8 Q8 bank weights × 96 coefficients, after verifying source symmetry. Synthetic tests intentionally perturb a selected region coefficient and a full high-ISO bank to prove that both violations are detected. CCT sampling is a regression test; the all-CCT statement rests on the componentwise interpolation and equal source entries.

Only sanitized booleans/counts/status and known source identities are retained publicly. The original full tuning array, firmware package, photo pixels and per-value outputs remain transient in CI.

## What this changes for the project

One dependency in the *audited static still profile* is now conditionally reducible: the unknown 16-region selector does not need to be solved **first** to know which six coefficients are available at a chosen CCT. The **six-coefficient pixel equation** itself remains the most significant blocker, followed by its input/output scale and ordering, gamma pixel evaluation, and MAIN 3D LUT sampling/working-space interpretation.

The active smartphone build remains Stage26 versionCode **27187**, which passed 11/11 JNI tests on-device (synthetic inputs, no RAW photograph). Stage27 changes only the research branch; no APK, camera capture, firmware table payload or saved-photo rendering is modified.

## Reproduction

From the repository root (no proprietary inputs required):

```bash
python3 hasselblad_native_audit/isp_main_stage27/audit_ccm_invariants27.py --self-test
```

Exact-source run in a controlled *private/transient* environment:

```bash
python3 hasselblad_native_audit/isp_main_stage27/audit_ccm_invariants27.py \
  --repo-root . \
  --firmware-root /private/X2DII_firmware_extracted \
  --output /private/STAGE27_CCM_INVARIANTS.json
```

The GitHub Actions workflow runs both and uploads only sanitized JSON. Do not paste firmware, IQ table, user DNG/JPEG or captured colour coefficients into an issue or public artifact.
