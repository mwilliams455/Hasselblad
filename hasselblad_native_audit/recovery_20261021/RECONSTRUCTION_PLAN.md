# AWB reconstruction plan

The previous session produced a long sequence of local-only AWB checkpoints whose source files were not durably published. Their conversation records are retained as historical targets, not as substitute source or fresh verification.

Rebuild in dependency order and re-run each boundary against the restored original firmware.

1. Original AWB initialization, calibrated locus/normalization, signed RAW reference.
2. Frame/statistics input contracts and responsive original scene-AWB replay.
3. Native E2 statistics manager/parser and generic scene input.
4. Per-block calibration, AE preparation and regular classification.
5. Scene weighting, connected-component filtering and candidate accumulation.
6. Candidate optimization and caller updates.
7. History processing and active correction/policy selection.
8. Atmosphere correction.
9. Post candidate preparation.
10. Calibrated colour-temperature/tint conversion and helpers.
11. Candidate publication, golden gains and history.
12. Dual synchronization and sensor gain helpers.
13. Gain validation/light-source selection.
14. Override window.
15. Smoothing and integer filters.
16. Result temperature/tint and gain snapshots.
17. Supported output tail through original post-processing return.
18. Compose the supported post controller.
19. Compose selected-scene estimator suffix.
20. Passive REAWB continuation.
21. Debug/shading/final outer confirmation and recovery.
22. Primary scene preparation and no-eligible-scene recovery.
23. General ordinary scene-controller loop.
24. Earlier frame preparation/initialization and remaining supported estimator assembly.

Each new checkpoint must clearly separate fresh original-code evidence, owned implementation behavior, authentic configuration behavior, synthetic branch coverage, and unsupported/optional branches.

## Product milestones after AWB recreation

- Restore Native1C capture-JSON/save-status behavior in source.
- Connect the complete supported estimator to phone RAW/statistics with a justified phone calibration contract.
- Preserve signed/headroom RAW-to-linear input and apply WB exactly once with a coherent matrix.
- Resolve remaining Hasselblad photographic per-pixel CCM/gamma/3D-LUT behavior.
- Integrate and validate actual saved photographs before claiming rendering parity.
