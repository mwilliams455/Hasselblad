package com.particlesdevs.photoncamera.hasselblad;

import android.view.Surface;
import android.hardware.camera2.CaptureRequest;
import java.util.Map;
import java.util.WeakHashMap;

/** Actual output configuration, keyed by the delivered ImageReader surface.
 * Weak keys avoid retaining closed readers. Entries are immutable snapshots. */
public final class HasselbladRawStream {
    private static final Map<Surface, Identity> streams = new WeakHashMap<>();
    private static final Map<CaptureRequest, Surface> requests = new WeakHashMap<>();
    public static final class Identity {
        public final String deviceId, physicalId;
        private Identity(String deviceId, String physicalId) {
            this.deviceId=deviceId; this.physicalId=physicalId;
        }
    }
    private HasselbladRawStream() {}
    public static synchronized void record(Surface surface, String deviceId, String physicalId) {
        if (surface != null && deviceId != null) streams.put(surface, new Identity(deviceId, physicalId));
    }
    /** Called immediately when the request with this explicitly added target is built. */
    public static synchronized CaptureRequest recordRequest(CaptureRequest request, Surface target) {
        if (target != null) requests.put(request, target);
        return request;
    }
    public static synchronized boolean requestTargets(CaptureRequest request, Surface target) {
        return target != null && target.equals(requests.get(request));
    }
    public static synchronized Identity lookup(Surface surface) { return streams.get(surface); }
}
