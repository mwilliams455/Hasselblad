# Research tooling and source provenance

The standalone app lives in the sibling `HasselbladPhoton` directory and retains
PhotonCamera's GPL-3.0 license and third-party notices. It is based on
`eszdman/PhotonCamera` commit `b2eff821a858033515eb2700e7292befecc95225`.

`cim_reader.py` comes from `devkit/cim.py` in
[derrickyau9/Hasselblad-X-System-QEMU-DevKit](https://github.com/derrickyau9/Hasselblad-X-System-QEMU-DevKit),
commit `d82dc3b0faa6456c260378df6352a07f929caed2`. Its original module was copied
with source/pin comments added. `extract_official.py` follows that project's
full-OTA reconstruction approach, adding regular-file-only extraction, both
partition manifests, and bounded input validation. These extraction files are
provided under the DevKit's AGPL-3.0-or-later terms; the complete license text is
included as `LICENSE-AGPL-3.0.txt`.

The DevKit builds on the original
[radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions](https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions)
research. That project is credited as an upstream research source; this bundle
does not replace either upstream project.

The original firmware remains an external input obtained from Hasselblad.
The CIM, extracted vendor/system libraries, camera tuning payloads, and camera
models are not included in this source bundle or the Native1 APK. Hashes,
function-level observations, proof results, and reproduction tools identify
the inputs used. A GPL or MIT notice on our host/probe code does not relicense
Hasselblad's original firmware.

The small new runtime probe C programs and `run_android_probes.py` are provided
under MIT, as identified in their source headers. The portable recovered WB
core and its Android JNI integration are supplied as source with the standalone
Photon project under the project's GPL-3.0 license. Existing third-party
copyright and license notices take precedence for their respective files.

Python package licenses accompany their distributions; exact observed versions
are listed in `requirements.txt`. Android SDK/NDK, JDK, Gradle, QEMU, and other
downloaded tool binaries are not redistributed in this source bundle.
