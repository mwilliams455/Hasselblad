# Firmware acquisition gate (not a claim of original validation)

Target: Hasselblad X2D II 100C firmware **1.3.16.2**.
The official manufacturer firmware listing remains available at
https://www.hasselblad.com/x-system/firmware/

The old in-memory extracted original is **not in the current workspace**.
The linked official download directory requires a dynamic product selection; a verified package/extracted `libaaa.so` has not been obtained during this checkpoint.

After restoring genuine firmware outside GitHub, compare extracted `system/lib64/libaaa.so` with the previously recorded SHA-256:
`7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`.
Do not copy the firmware, vendor calibration tables or original code into the GitHub repo. Set up a same-execution ARM64 comparison with the reconstructed owned implementation and preserve the discovered ABI and independent test results as safe notes.