# Hasselblad Photon — conversation AWB research ledger

**Prepared:** 21 October 2026  
**Purpose:** Preserve the detailed AWB research progression recorded in the ChatGPT conversation after the corresponding unpublished local source workspace was lost.

> **Important boundary:** This document is a historical research ledger reconstructed from the conversation record. It preserves checkpoint names, commit hashes, claimed verification results, stage boundaries, and technical findings. It is **not** a replacement for the missing C/C++/Java source, test harnesses, original Git objects, or raw firmware evidence. Every rebuilt stage must be reimplemented and freshly revalidated against the restored original firmware before it is treated as recovered code.

## Durable material that exists separately

The following items are durably preserved in ChatGPT Library and/or GitHub:

- `HasselbladPhoton_Native1A_Source_and_Validation (1).zip` — preserved Native1A source/validation baseline.
- `hasselblad.zip` — Native1C returned capture bundle used for metadata/device validation.
- `Hasselblad_Photon_Handoff_2026-10-20_AWB_Next.md` and copies — morning Native1C/metadata handoff.
- `Hasselblad_Recovery_Record_2026-10-20.txt` — recovery history, source/firmware identities, and later checkpoint summary.
- `Hasselblad_Environment_Checkpoint_2026-10-20.zip` — reconstructed build/original-code comparison environment evidence.
- GitHub recovery branches created 21 October 2026:
  - `awb-recovery-20261021`
  - `recovery/awb-rebuild-20261021`

The detailed AWB checkpoint directories referenced below were **not** found as separate Library files after the workspace loss.

## Conversation-recorded AWB checkpoint sequence

### 1. Scene weighting, filtering, and candidate accumulation

**Recorded local commit:** `d7f6c48`  
**Recorded title:** `Reconstruct regular AWB scene weighting, filtering and accumulation`

Conversation-recorded findings:

- Scene weighting reproduced classifier/zone behavior, including zone rules assigning weight to blocks skipped by the ordinary classifier.
- Connected-component filtering removed groups containing three blocks or fewer and preserved original traversal/edge behavior.
- Candidate accumulation combined surviving weighted blocks into scene candidates.
- Complete scene-context comparison reportedly matched all **920,560 bytes** at **28 comparison points**: 21 individual-stage checks and seven complete-chain checks.
- Reported direct coverage included 192 weighting cases, 192 filtering cases, and prepared accumulation comparisons.
- Observer-free control and independent reviews were reported as passing.

Historical path references:

- `hasselblad_native_audit/awb_scene_20261020/`
- `SCENE_PIPELINE_FINDINGS.md`
- `AWB_SCENE_CHECKPOINT.md`
- `NEXT_SESSION.md`

### 2. Scene candidate optimization

**Recorded local commit:** `9a9f7a1c5105bbad0ed2596d4ee375589355614c`  
**Recorded title:** `Reconstruct AWB scene optimization and verify original caller integration`

Conversation-recorded findings:

- Implemented scene candidate optimizer and temperature lookup/conversion.
- Preserved caller-side count updates made after optimizer return.
- Reported verification:
  - 256 successful optimizer original-reference cases.
  - 512 temperature-conversion original-reference cases.
  - 34 combined-pipeline checks.
  - Seven-frame full-context comparisons at the optimizer/caller boundary.
- History processing (`scene_awb_hist_proc`) identified as the next stage.

Historical path:

- `hasselblad_native_audit/awb_optimization_20261020/`

### 3. Bounded history-processing path

**Recorded local commit:** `0ca6c2f24ea82f572a3671a53b46906a8552f96a`  
**Recorded title:** `Reconstruct bounded AWB history and verify atmosphere handoff`

Conversation-recorded findings:

- Reconstructed the history path exercised by the reference sequence, where policies rejected before active correction.
- Added supporting temperature-distance, coordinate-remapping, interpolation, and zone-geometry functions.
- Reported verification:
  - 256 successful history comparisons covering 414 active illumination slots.
  - 1,024 synthetic scalar comparisons plus authentic-initialization queries.
  - 4,640 zone-geometry comparisons.
  - Seven complete-context comparisons after history and seven at atmosphere entry.
- Active history correction remained the next target.

Historical path:

- `hasselblad_native_audit/awb_history_20261020/`

### 4. Active history correction and policy selection

**Recorded local commit:** `ef32d015d93f8488956c78cc6b7ac2b9989893d4`  
**Recorded title:** `Reconstruct active AWB history correction and policy selection`

Conversation-recorded findings:

- Implemented histogram-support ratios, active correction interpolation, policy selection, and publication.
- Combined and measured WB could select different policies.
- Preserved original 32-bit wrap/rounding behavior.
- Reported verification:
  - **784** whole-function fixtures.
  - **846** active illumination slots.
  - **732** nonidentity publications/selection updates.
  - Complete **920,560-byte** context comparisons.
  - Histogram helper and policy-selection comparisons.
- Atmosphere processing became the next target.

Historical path:

- `hasselblad_native_audit/awb_hist_correction_20261020/`

### 5. Atmosphere correction

**Recorded local commit:** `557c549520046180436ac993a23c177a474ab3d3`  
**Recorded title:** `Reconstruct mode-zero AWB atmosphere correction and post handoff`

Conversation-recorded findings:

- Reconstructed ordinary atmosphere correction, label-based correction, and eND correction for supported mode-zero behavior.
- Preserved signed comparison and rounding details.
- Reported verification:
  - 481 successful complete-stage comparisons.
  - 623 active illumination slots and 560 changed coordinate pairs.
  - 3,072 ordinary/eND helper comparisons.
  - 1,536 label-helper comparisons.
  - Seven-frame original pipeline handoff to post processing.

Historical path:

- `hasselblad_native_audit/awb_atmosphere_20261020/`

### 6. Post candidate preparation

**Recorded local commit:** `842e61279d7931c82769dcb1df55b7ab5ede3a9f`  
**Recorded title:** `Reconstruct automatic AWB post candidate preparation and reAWB handoff`

Conversation-recorded findings:

- Reconstructed ordinary/special illumination selection, temporal caches, candidate weighting, spectral fusion, and override handling.
- Preserved different cache-copy lengths, retained weights, and special-illumination fallback order.
- Reported verification:
  - 384 candidate-preparation comparisons against original firmware.
  - 4,608 supporting-helper comparisons.
  - Seven authentic full-context candidate-boundary matches.
  - Seven handoff matches to the following AWB stage.

Historical path:

- `hasselblad_native_audit/awb_post_20261020/`

### 7. Calibrated colour temperature and tint

**Recorded local commit:** `edc1aaf`  
**Recorded title:** calibrated CT reconstruction checkpoint.

Conversation-recorded findings:

- Implemented gain-to-CT/tint conversion, calibrated matrix interpolation/inversion, eND/remapping paths, black-body conversion, and convergence loop.
- Reported verification:
  - **512/512** complete CT calculations matched exact temperature/tint/status/iteration behavior.
  - **5,952** total matrix iterations matched.
  - **2,560/2,560** helper comparisons.
  - **30/30** actual CT/tint calls in the initialized pipeline.
  - Ten downstream complete-context comparisons.

Historical path:

- `hasselblad_native_audit/awb_calibrated_ct_20261020/`

### 8. Candidate publication and golden gains

**Recorded local commit:** `edf4f449183613cec2d5fb39cff73597e3910f01`

Conversation-recorded findings:

- Reconstructed ordered CT/tint publication, golden gain scaling, and candidate/history copies.
- Any nonzero validity byte admitted publication; only exact value `1` triggered history copy.
- Later failures preserved earlier successful publications.
- Reported verification:
  - 384 prepared publication cases, including 43 error cases.
  - 1,139 golden-gain helper comparisons.
  - Five complete pipeline state snapshots.

Historical path:

- `hasselblad_native_audit/awb_publication_20261020/`

### 9. Dual synchronization

**Recorded local commit:** `518b25740e2dde91c3229b65bff3faf9444047a3`

Conversation-recorded findings:

- Reconstructed sync gates, sensor CT/tint conversion, zone gain adjustment, gain blending, clamps, and red/blue publication.
- Outer wrapper could return success while an inner operation reported an error; partial sensor state could remain.
- Authentic five valid reference frames had dual sync disabled by genuine gates.
- Reported verification:
  - 552 complete calculation/wrapper comparisons.
  - 2,624 intermediate helper-call boundaries.
  - 1,024 sensor/zone/gain-shift helper comparisons.
  - 512 CT/tint-to-gain comparisons plus 26 review edge cases.

Historical path:

- `hasselblad_native_audit/awb_dual_sync_20261020/`

### 10. Gain validation and light-source selection

**Recorded local commit:** `8037d8861a8283300cc476155d07e295fb5ca1a4`

Conversation-recorded findings:

- Reconstructed six-gain validation and automatic/manual/clear light-source selection.
- Preserved score/tie behavior and manual-label flag interaction.
- Authentic reference route actively selected a light source on all five valid frames.
- Reported verification:
  - 384 direct original light-source calls.
  - 384 original gain-validation-window executions.
  - 256 zone-classification helper comparisons.
  - 20 extra edge cases.

Historical path:

- `hasselblad_native_audit/awb_light_source_20261020/`

### 11. Override window

**Recorded local commit:** `6904ece665bc052c46935d8310568c45540d890e`

Conversation-recorded findings:

- Reconstructed both requested-WB conversions, retain/replace decision, gain publication, history updates, and override clearing.
- Authentic five valid reference frames skipped the override.
- Reported verification:
  - 192 prepared original-firmware runs: 96 skips, 34 retain, 62 replace.
  - Optimized/sanitizer checks and three independent reviews.

Historical path:

- `hasselblad_native_audit/awb_override_20261020/`

### 12. Smoothing and integer filters

**Recorded local commit:** `4f9a65f237bcdffe4c015a01bf48ea7a42bbda5a`

Conversation-recorded findings:

- Reconstructed smoothing controller, two filtered-gain sets, persistent transition state, and integer filter.
- Authentic seven-frame sequence reached smoothing on five frames: one initialization and four filtered frames.
- Reported verification:
  - 768 complete smoothing comparisons.
  - 368 integer-filter comparisons.
  - Five authentic full-pipeline matches at smoothing.

Historical path:

- `hasselblad_native_audit/awb_smoothing_20261020/`

### 13. Result CT/tint and gain snapshots

**Recorded local commit:** `7e4a62d95f9c5a6b7b6039c29605a5b84b4660a7`

Conversation-recorded findings:

- Reconstructed four result CT/tint calculations in fixed order plus raw-gain snapshot.
- Later calculation failures preserved earlier result writes.
- Reported verification:
  - 320 complete colour-temperature function calls.
  - 245 complete gain-snapshot calls.
  - 1,049 calibrated-helper calls.
  - Five authentic frames reached these stages.

Historical path:

- `hasselblad_native_audit/awb_result_ct_20261020/`

### 14. Supported output tail

**Recorded local commit:** `2b7b7bc`

Conversation-recorded findings:

- Reconstructed final gain recalibration, normalization, optional-branch decisions for reference configuration, diagnostic publication, candidate validation, and CT clamp to 2000–10000 K.
- Intermediate recalibration errors could still end in successful final return after validation.
- Reported verification:
  - 256 prepared output-tail cases.
  - 128 standalone final-validation cases.
  - 224 separate original helper calls.
  - 33/33 reference-pipeline checks.

Historical path:

- `hasselblad_native_audit/awb_output_tail_20261020/`

### 15. Complete supported post-processing controller

**Recorded local commit:** `5f2a085`

Conversation-recorded findings:

- Composed eight recovered post stages into one controller including invalid-candidate recovery.
- Reported verification:
  - 104 complete original firmware calls.
  - Full 920,560-byte state plus return status.
  - Eight successive frames carrying persistent state.
  - All seven reference frames including two recovery frames.
  - 29 owned input/unsupported-feature rejection checks.

Historical path:

- `hasselblad_native_audit/awb_post_controller_20261020/`

### 16. Selected-scene estimator suffix

**Recorded local commit:** `f717e482da9eb1d57089579980d5d6b9857132f4`

Conversation-recorded findings:

- Composed selected-scene weighting/optimization/history/atmosphere/post stages.
- Preserved cross-stage block-usage counts and state handoffs.
- Reported verification:
  - Seven complete firmware frames matched entire 920,560-byte state and return status.
  - Eight completion cases and 51 atomic rejection cases.

Historical path:

- `hasselblad_native_audit/awb_estimator_suffix_20261020/`

### 17. Passive REAWB continuation

**Recorded local commit:** `96ca17c3a9f81ee559eb66802cba56492dbcfda1`

Conversation-recorded findings:

- Implemented three complete passive REAWB routes and its 1,000-byte persistent handle behavior.
- Even disabled REAWB could save state before checking its switch.
- Active linked-history REAWB remained unsupported.
- Reported verification:
  - 96/96 complete original REAWB calls.
  - Seven-frame comparison across full context, handle, and return status.
  - 52/52 integration checks.

Historical path:

- `hasselblad_native_audit/awb_reawb_20261020/`

### 18. Debug, shading, final confirmation, and outer recovery

**Recorded local commit:** `328b65f4c811cd81f986f18ea66d41fd6e1b34e9`

Conversation-recorded findings:

- Reconstructed diagnostic backup/restoration/encryption/statistics packing, shading-temperature selection, and final result confirmation/recovery.
- Verified post status 151 recovery: skip later processing, restore confirmed results, finish outer status 0.
- Reported verification:
  - Seven unchanged frames matched 920,560 context bytes, 1,000 handle bytes, and final status.
  - 80 debug calls, 84 shading calls, and 24 result-copy calls.
  - Separate complete native recovery witness.

Historical path:

- `hasselblad_native_audit/awb_outer_completion_20261020/`

### 19. Primary scene preparation and no-eligible-scene recovery

**Recorded local commit:** `aded05ef2f87402c051dd5746e6c58585bffe2b5`

Conversation-recorded findings:

- Extended the owned entry earlier than weighting to spectral preparation and primary-scene eligibility.
- Implemented complete no-eligible-scene recovery: scene status 40, skip later stages, restore confirmed results, outer status 0.
- Supported success path remained bounded to ordinary illumination 0 with scene 3 as sole eligible scene.
- Reported verification:
  - Seven unchanged frames matched complete context, 1,000-byte handle, and final status.
  - 82/82 integration checks.
  - 80 direct spectral-preparation calls and 32 calls through controller.
  - 32 no-eligible-scene controller calls.
  - Separate native recovery test 26/26.

Historical path:

- `hasselblad_native_audit/awb_scene_entry_20261020/`

This was the **last recorded local checkpoint before workspace loss**.

## Additional research that predates the visible checkpoint sequence

The conversation and recovery plan also reference several earlier missing AWB research stages that are not fully reproduced in this ledger because their detailed files/source were not preserved in Library:

- AWB library initialization and authentic calibration-table setup.
- Frame/statistics input contract and responsive original scene-AWB replay.
- Native E2 statistics manager/parser.
- Generic scene input and per-block calibration.
- AE preparation and regular classification.
- Signed RAW reference/clean linear-input work.

These are explicitly included in the GitHub reconstruction plan so they are rebuilt before later stages that depend on them.

## What is genuinely preserved vs. what must be rebuilt

### Preserved durably

- This conversation's textual research history and checkpoint descriptions.
- Commit hashes/names and many comparison counts/results recorded above.
- Native1A source archive and published GitHub baseline.
- Native1C returned capture bundle.
- Morning Native1C/metadata handoff.
- Recovery and rebuilt-environment records.
- GitHub recovery/rebuild branches and their current recovery documentation.

### Not preserved as executable/source proof

- The source tree for the 19 later AWB local commits listed above.
- Their exact original test harnesses and binaries.
- Their checkpoint manifests/review files unless recreated.
- The original local Git objects for those commits.

## Reconstruction rule

Treat every historical claim above as a **target to reproduce**, not as a substitute for rerunning the original-vs-owned tests. As each stage is rebuilt, replace the historical-only status with a new GitHub checkpoint containing source, reproducible test code, fresh execution reports, and explicit source/firmware identities.
