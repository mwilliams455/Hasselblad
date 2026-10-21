package com.particlesdevs.photoncamera.hasselblad;

/** Latest capture evidence save outcome, in-memory for this app session only. */
public final class HasselbladCaptureSaveStatus {
    private static volatile Snapshot latest = new Snapshot("skipped",
            "No capture JSON attempt during this session.", "");

    public static final class Snapshot {
        public final String state;
        public final String message;
        public final String fileName;

        private Snapshot(String state, String message, String fileName) {
            this.state = state;
            this.message = message;
            this.fileName = fileName;
        }

        public String display() {
            return "Capture JSON: " + state + "\n" + message +
                    (fileName.isEmpty() ? "" : "\n" + fileName) + "\n\n" + HasselbladSceneDiagnostics.latestSummary();
        }
    }

    private HasselbladCaptureSaveStatus() {}

    public static Snapshot latest() { return latest; }

    public static void started() { latest = new Snapshot("pending", "Capturing original metadata and scene diagnostics.", ""); }

    public static void saved(String name) {
        latest = new Snapshot("saved", "Capture metadata was written using the granted DCIM storage access.", safe(name));
    }

    public static void failed(String reason, String name) {
        latest = new Snapshot("failed", safe(reason), safe(name));
    }

    public static void skipped(String reason) {
        latest = new Snapshot("skipped", safe(reason), "");
    }

    private static String safe(String text) { return text == null ? "" : text; }
}
