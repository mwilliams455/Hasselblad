#include <jni.h>
#include <stdint.h>
#include <stdio.h>

#include "hb_awb_recalib.h"

/* This bridge calls our audited portable reconstruction, not a vendor library. */
JNIEXPORT jlongArray JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladNativeCheck_nativeRecalibrate(
        JNIEnv *env, jclass type, jlong gain_a, jlong gain_b,
        jlong calibration_a, jlong calibration_b)
{
    (void) type;
    const jlong inputs[] = {gain_a, gain_b, calibration_a, calibration_b};
    for (unsigned int i = 0; i < 4; ++i) {
        if (inputs[i] < 0 || (uint64_t) inputs[i] > UINT32_MAX) {
            jclass exception = (*env)->FindClass(env, "java/lang/IllegalArgumentException");
            if (exception != NULL) {
                (*env)->ThrowNew(env, exception, "AWB primitive inputs must be unsigned 32-bit integers");
            }
            return NULL;
        }
    }
    hb_awb_q12_pair input = {(uint32_t) gain_a, (uint32_t) gain_b};
    hb_awb_q12_pair calibration = {(uint32_t) calibration_a, (uint32_t) calibration_b};
    hb_awb_recalib_result result = hb_awb_recalib_portable(input, calibration);
    jlong values[] = {
        result.adapter_status, result.original_called, result.original_status,
        result.output.a, result.output.b
    };
    jlongArray output = (*env)->NewLongArray(env, 5);
    if (output != NULL) {
        (*env)->SetLongArrayRegion(env, output, 0, 5, values);
    }
    return output;
}

JNIEXPORT jstring JNICALL
Java_com_particlesdevs_photoncamera_hasselblad_HasselbladNativeCheck_nativeProvenance(
        JNIEnv *env, jclass type)
{
    (void) type;
#if defined(__aarch64__)
    const char *abi = "arm64-v8a";
#elif defined(__arm__)
    const char *abi = "armeabi-v7a";
#elif defined(__x86_64__)
    const char *abi = "x86_64 (host bridge check)";
#else
    const char *abi = "unknown";
#endif
    char text[640];
    (void) snprintf(text, sizeof(text),
        "Executing: portable C reconstruction through JNI\n"
        "Native library: libhasselblad_wb_jni.so\n"
        "Native ABI: %s\n"
        "Evidence firmware: %s\n"
        "Original routine: %s\n"
        "Original ELF: %s\n"
        "Original routine address: 0x%06x (%u bytes)\n"
        "Original ELF SHA-256: %s\n"
        "The original vendor library is not loaded by this check.",
        abi, HB_AWB_FIRMWARE, HB_AWB_SYMBOL, HB_AWB_LIBRARY,
        HB_AWB_SYMBOL_VA, HB_AWB_SYMBOL_BYTES, HB_AWB_LIBRARY_SHA256);
    return (*env)->NewStringUTF(env, text);
}
