#ifndef PHOTON_DNG_FIXTURE_ANDROID_LOG_H
#define PHOTON_DNG_FIXTURE_ANDROID_LOG_H

#define ANDROID_LOG_DEBUG 3
#define ANDROID_LOG_ERROR 6

#ifdef __cplusplus
extern "C" {
#endif
int __android_log_print(int priority, const char* tag, const char* format, ...);
#ifdef __cplusplus
}
#endif

#endif
