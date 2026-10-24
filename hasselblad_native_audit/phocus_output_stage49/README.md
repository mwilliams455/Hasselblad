# Stage49: native working-space parameters and SDR output conversion

Stage48 found a saturated-blue coordinate limit in the base colour grid.
Stage49 checks the native routes as coupled configurations and measures the
actual built-in CPU output converter, without fitting a photograph or changing
the application's look.

## Results

The original Android colour and film `UpdateParameters` bodies passed 36 cases:
working-space codes 0–5, film codes 0/1, and 2850/4000/5550 K. The emitted input
and output matrices, float LUTs, coordinate bounds and 65,536-entry normalized
film tables matched the independent reconstruction exactly.

Space 0 selects companding 1 and the 105×89 grid. Nonzero spaces select
companding 2 and the 165×108 grid, together with their corresponding output
matrices. Film codes 0 and 1 produce exactly the same table in the tested
nonzero spaces. A larger grid with the old space-0 output matrix/transfer is
therefore only a diagnostic, not the native alternative route.

The original `CCustomCMM` constructor, matrix calculation, uint16 wrapper,
float converter, linearization and output encoding executed for special
profiles 0 and 1 to profile 2. These are separate enum values from working
space. Profile 2 has the sRGB primaries and sRGB transfer. Profile 0 uses a
2.19921875 decoding exponent; profile 1 uses L* decoding. Native matrix
composition agreed with an independent primaries/white-point/Bradford
calculation within 8.89e-16.

Each output route passed 5,426 synthetic encoded RGB/neutral pixels. All
32,556 output channels matched the independent uint16 conversion exactly.
Native replays of 4,096 existing room samples for each of three curves also
matched exactly: another 36,864 channels. The complete room frames below were
evaluated with that validated reconstruction, not replayed in their entirety.

## Difference from the current adapter

The current space-0 decoding exponent is correct. Two small differences were
measured: the built-in profile matrix differs from the independently derived
adapter by at most 0.0021862, and the native uint16 converter normalizes by
65,535 rather than the adapter's 65,536.

| Existing rendered codes | Mean channel change, /255 | Maximum change, /255 |
| --- | ---: | ---: |
| Synthetic encoded cube and neutral ramp | 0.08816 | 5 |
| Room, film 0 / 3050 K | 0.02770 | 2 |
| Room, film 0 / 4000 K | 0.02761 | 2 |
| Room, film 1 / 4000 K | 0.02465 | 3 |

These results do not support the output adapter as the main cause of the room's
perceived lack of Hasselblad character. No aesthetic correction, profile
replacement or APK change follows from this audit.

## Scope and next boundary

Original parameter preparation receives a prepared native RAW colour object
through a recording factory fixture. Lens reduction and destruction remain
fixtures. CMM allocation and libm use the established host fixtures. Buffer
guards and input immutability pass; the source APK is unchanged.

Static inspection of `VerifyDefaultInputProfile` associates working spaces
0/1 with `kHasselBladDeviceProfile` / `kHasselBladDeviceProfileLStar`.
`GetInputProfile` starts with special profile 0 as its fallback, and the preview
output-filter builder requests destination special profile 2. This is not a
recording of the running app's selected settings or an executed display graph.

The complete live Android/GPU display route remains unverified. In particular,
the separate colour-space shader and CPU filter have transfer-handling
differences, so their equivalence must not be assumed. The next output task is
to bind the actual SDR filter sequence, transfer ownership and surface format.
Phone sensor adaptation also remains experimental; passing these arithmetic
checks does not establish photographic equivalence across sensors or lights.

## Reproduction and privacy

Run `audit_output49.py --apk OWNER_APK --profile SPACE0_HBC --out PRIVATE_DIR
--safe-receipt SAFE_JSON`, optionally supplying `--room-java PRIVATE_STAGE46_DIR`.
The owner APK is hash-pinned by the existing private-input loader. Assertions
must be enabled. Use the existing Stage45 Python/emulation dependencies.

Only independent source and aggregate evidence belong in GitHub. The emitted
`Stage49_Private_Output_Reference.npz` contains recovered private matrices and
transfer definitions; keep it private. It is research data, not an importable
phone colour profile. No APK, vendor binary, LUT, camera matrix, image or
private-input digest is included in this stage's public evidence.
