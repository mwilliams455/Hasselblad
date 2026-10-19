// Compile the actual app creator and retained TIFF writer on the host. Only
// Android logging is stubbed; no sample-writing or metadata code is replaced.
#include <filesystem>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <vector>

#include PHOTON_DNG_SOURCE

extern "C" int __android_log_print(int, const char*, const char*, ...) {
    return 0;
}

static void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}

static void writeFile(const std::filesystem::path& path, const void* data, size_t bytes) {
    std::ofstream stream(path, std::ios::binary);
    stream.write(static_cast<const char*>(data), static_cast<std::streamsize>(bytes));
    require(stream.good(), "Could not write fixture output");
}

static void makeCase(const std::filesystem::path& dir, const char* name,
                     double white, unsigned short bps, bool compressed) {
    constexpr int width = 32;
    constexpr int height = 24;
    const unsigned int level = static_cast<unsigned int>(white);
    std::vector<uint16_t> samples(width * height);
    for (size_t i = 0; i < samples.size(); ++i) {
        samples[i] = static_cast<uint16_t>((i * 97u + (i / width) * 13u) % (level + 1u));
    }
    samples[0] = 0;
    samples[1] = 64;
    samples[2] = static_cast<uint16_t>(level);
    writeFile(dir / (std::string(name) + ".input.bin"), samples.data(), samples.size() * 2);

    DngCreator creator;
    creator.setWhiteLevel(white);
    const unsigned short black[4] = {64, 64, 64, 64};
    creator.setBlackLevel(black);
    creator.setBitsPerSample(bps);
    creator.setCompression(compressed);
    creator.setOrientation(6);
    creator.setCFAPattern(0);
    creator.setMake("Fixture");
    creator.setModel("Synthetic RAW samples");
    creator.setUniqueCameraModel("Native1A export regression fixture");
    creator.setSoftware("Hasselblad Photon writer fixture");
    creator.setDateTime("2026:10:19 00:00:00");
    size_t bytes = 0;
    void* encoded = creator.createDng(samples.data(), width, height, bytes);
    require(encoded != nullptr && bytes > 0, "Actual app DNG creation failed");
    writeFile(dir / (std::string(name) + ".dng"), encoded, bytes);
    std::free(encoded);
    writeFile(dir / (std::string(name) + ".after.bin"), samples.data(), samples.size() * 2);
}

#ifdef NATIVE1A_GUARDS
static void checkGuards(const std::filesystem::path& dir) {
    const double invalid[] = {
        std::numeric_limits<double>::quiet_NaN(),
        std::numeric_limits<double>::infinity(),
        -std::numeric_limits<double>::infinity(),
        -1.0, 1023.5, 4294967296.0
    };
    int rejected = 0;
    for (int bps : {16, 10}) {
        for (double level : invalid) {
            DngCreator creator;
            creator.setBitsPerSample(bps);
            creator.setCompression(false);
            creator.setWhiteLevel(level);
            std::vector<uint16_t> samples(16, 64);
            size_t bytes = 123;
            void* encoded = creator.createDng(samples.data(), 4, 4, bytes);
            require(encoded == nullptr && bytes == 0,
                    "Unrepresentable WhiteLevel was not rejected through the native failure path");
            require(samples == std::vector<uint16_t>(16, 64),
                    "Rejected metadata changed the input samples");
            ++rejected;
        }
    }
    int accepted = 0;
    for (double level : {0.0, 1023.0, 65535.0, 4294967295.0}) {
        require(photon_dng::isIntegralWhiteLevel(level),
                "Representable unsigned LONG boundary was rejected");
        ++accepted;
    }
    const std::string result = "{\"invalid_native_calls_rejected\":" + std::to_string(rejected)
            + ",\"representable_boundaries_accepted\":" + std::to_string(accepted) + "}\n";
    writeFile(dir / "guards.json", result.data(), result.size());
}
#endif

int main(int argc, char** argv) {
    require(argc == 2, "Usage: dng_export_fixture output-directory");
    const std::filesystem::path dir(argv[1]);
    std::filesystem::create_directories(dir);
    makeCase(dir, "raw16_1023", 1023, 16, false);
    makeCase(dir, "raw16_65535", 65535, 16, false);
    makeCase(dir, "jpeg16_1023", 1023, 16, true);
    makeCase(dir, "jpeg16_65535", 65535, 16, true);
    makeCase(dir, "raw10_1023", 1023, 10, false);
    makeCase(dir, "raw10_linearized_4095", 4095, 10, false);
#ifdef NATIVE1A_GUARDS
    checkGuards(dir);
#endif
    return 0;
}
