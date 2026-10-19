#ifndef PHOTONCAMERA_DNGWHITELEVEL_H
#define PHOTONCAMERA_DNGWHITELEVEL_H

#include <cmath>
#include <limits>

#include "deps/tiny_dng_writer.h"

namespace photon_dng {

// DNG WhiteLevel (50717) accepts SHORT or LONG, not RATIONAL. Camera2 levels
// are integral; reject unrepresentable metadata instead of rounding the level.
inline bool isIntegralWhiteLevel(double value) {
    static_assert(std::numeric_limits<unsigned int>::digits == 32,
                  "The retained TIFF writer requires a 32-bit unsigned LONG");
    return std::isfinite(value) && value >= 0.0 &&
           value <= std::numeric_limits<unsigned int>::max() &&
           std::floor(value) == value;
}

inline bool setWhiteLevel(tinydngwriter::DNGImage& image, double value) {
    return isIntegralWhiteLevel(value) && image.SetCustomFieldULong(
            static_cast<unsigned short>(tinydngwriter::TIFFTAG_WHITE_LEVEL),
            static_cast<unsigned int>(value));
}

}  // namespace photon_dng

#endif  // PHOTONCAMERA_DNGWHITELEVEL_H
