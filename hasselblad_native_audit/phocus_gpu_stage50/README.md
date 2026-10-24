# Stage50: Android SDR output boundaries and original GLES kernels

This stage resolves the Stage49 CPU/GPU transfer question for explicit SDR
settings fixtures. It does not change the Photon app or fit the room image.

## Native graph selection

The original `CameraImageAndroid::AddHNCSFilters` body executed six cases:
working spaces 0/1, SDR tool code 2, optional edits disabled, and three output
flag combinations. Filter construction, parameter updates and shared ownership
were recording fixtures; the builder's selection and ordering were original.

The recorded sequence was colour correction, film curve, gradation, then output
conversion unless explicitly skipped. With both stack flags false, the output
parameters were colour-space code 1, white-point code 0, transfer code 3. This
is the D50-adapted P3 matrix with no output transfer. The alternate output flag
selected space 2 and transfer 4, a 2.19921875 power encoding. These flags are
not bound to live app UI settings in this audit.

Original output initialization and matrix preparation executed. Original
texture-format accessors returned GL_RGBA16F for both texture codes 7 and 8.
The selected linear output is therefore a processing boundary, not a finished
sRGB image. Final Android surface tagging/compositor behaviour remains open.

## Actual shader execution

The owner's original fragment shaders were loaded directly from the hash-pinned
APK and executed unchanged on headless OpenGL ES 3.2, Mesa llvmpipe. Both input
and output textures used RGBA16F. This is software GLES, not the user's phone GPU.
The test set contained 4,913 encoded RGB cube points and 513 neutral samples.

For the selected HNCS output configurations, shader error against independent
math was below 0.000976 in float output. The original CPU output method matched
its double-precision reconstruction within 8.33e-16 on the sampled pixels.
CPU/GPU values, when quantized for comparison, differed by at most 1/255. The
shader decodes with 2.2 while the CPU uses 2.19921875; half-float storage also
accounts for numerical differences.

For a controlled whole-frame diagnostic, the native linear-P3 shader output
was converted through its corresponding XYZ basis and standard sRGB. That final
adapter is ours; Android presentation was not executed.

| Existing rendered codes | Mean channel difference, /255 | Maximum, /255 |
| --- | ---: | ---: |
| Room, film 0 / 3050 K | 0.08551 | 1 |
| Room, film 0 / 4000 K | 0.08521 | 1 |
| Room, film 1 / 4000 K | 0.07639 | 2 |

These differences do not support changing output gamma to obtain a stronger
photographic look. The current space-0 SDR adapter remains the baseline.

## Two native mismatches, with separate scope

1. **Alternate L* profile:** the original `CCustomCMM::SupportsGpu` returned true
   for special profile 1 to special profile 2. The complete original GPU
   parameter body then selected `CustomCMM`, texture code 8, and transfer-in
   code 5. Its shader only implements transfer-in codes 1 and 2, so L* decoding
   was skipped. Against the verified CPU transfer math, the shader differed by
   an average 47.33 and maximum 214/255 on the synthetic set. Normal special
   profile 0 differed by at most 1/255. Working-space enums and special-profile
   enums are distinct. Our current viewer uses the space-0 CPU path and is not
   affected by this demonstrated alternate-profile mismatch.
2. **Unselected sRGB enum:** the separate colour-space shader leaves transfer
   code 1 linear, while its CPU method applies sRGB encoding. The diagnostic
   difference was as large as 74/255. The tested SDR graph selected code 3 or
   4, not code 1. This does not establish a defect in the live app's selected
   display route.

The native GPU entry point and shader are therefore not interchangeable with
the CPU reference for every configuration. Do not adopt the expanded/L* route
or copy the native GPU implementation blindly as a colour improvement.

## Next work and bounds

Keep the verified space-0 output stable. The next colour investigation should
address input preparation/adaptation and default gradation across controlled
inputs and illuminants. Phone sensor adaptation is still experimental. Actual
live app flags, full RAW processing, the final presentation chain, and a
matched photographic Hasselblad reference have not been validated here.

GPU handler/task/texture ownership were recording fixtures during ARM64
parameter replay. Actual kernel execution used an independent GLES harness;
the original Android GL lifecycle was not executed. Host allocation, libm and
logging fixtures remain explicit. No photographic colour coefficients were
fitted, source inputs were not modified, and no APK was built.

Run `audit_gpu50.py --apk OWNER_APK --profile SPACE0_HBC --safe-receipt SAFE_JSON`,
optionally adding `--room-java PRIVATE_STAGE46_DIR`. Use the Stage49 Python
dependencies plus a working EGL/Mesa software GLES implementation. Assertions
must be enabled. No vendor shaders, binary, calibration arrays, private input
hashes or user pixels are included in the public source/evidence.
