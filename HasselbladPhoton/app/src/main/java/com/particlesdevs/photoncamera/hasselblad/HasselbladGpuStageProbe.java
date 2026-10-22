package com.particlesdevs.photoncamera.hasselblad;

import android.opengl.GLES30;
import android.util.Base64;
import com.particlesdevs.photoncamera.processing.opengl.GLTexture;
import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Stage6: one explicitly armed Bayer2Float GPU readback on its owning GL thread.
 * Never selects WB, modifies RAW, publishes a neutral, rerenders, or touches
 * the shader. Samples total at most 4 KiB plus bounded GL staging;
 * only 16 isolated 8x8 patches are read.
 * The exact physical camera/frame/timestamp comes from the original proven
 * RAW metadata in HasselbladCaptureEvidence, NOT from a current camera ID.
 */
public final class HasselbladGpuStageProbe {
    private static boolean armed;
    private static long epoch;
    private static volatile String latest = "{\"schema\":\"hb-stage6-gpu-v1\",\"status\":\"not_armed\"}";
    private HasselbladGpuStageProbe() { }

    public static synchronized void arm() {
        if (latest.contains("\"status\":\"pending\"")) return;
        epoch++;
        armed = true;
        latest = "{\"schema\":\"hb-stage6-gpu-v1\",\"status\":\"armed_next_eligible_raw\","
                + "\"render_applied\":false}";
    }
    public static synchronized boolean isArmed() { return armed; }
    public static String latestJson() { return latest; }
    public static String status() {
        try {
            JSONObject obj = new JSONObject(latest);
            String state = obj.optString("status", "unknown");
            if (state.equals("completed"))
                return "Stage6 completed: 1,024 Bayer2Float GPU samples. Copy JSON, "
                        + "then pair it with this capture's original DNG and .capture.json.";
            if (state.equals("armed_next_eligible_raw"))
                return "Stage6 armed. Return to the camera and take one ordinary "
                        + "RAW+JPEG photo, then open this screen again.";
            if (state.equals("pending"))
                return "Stage6 capture bound; waiting for Bayer2Float GPU output.";
            return "Stage6: " + state + (obj.has("reason")
                    ? " (" + obj.optString("reason") + ")" : "")
                    + ". Photon colour is unchanged.";
        } catch (Exception ignored) {
            return "Stage6 diagnostic has no valid status.";
        }
    }
    private static synchronized void skipped(String reason) {
        JSONObject j = baseReport("skipped");
        try { j.put("reason", reason); } catch (Exception ignored) {}
        latest = j.toString();
    }

    public static synchronized Session claim(JSONObject identity, int width, int height,
                                             int cfa, int frames, boolean crop,
                                             boolean alreadyProcessed, boolean bayerRgb,
                                             float[] neutral, int whiteLevel, float[] black) {
        if (!armed) return null;
        armed = false; // exactly one attempt, whether usable or not
        if (identity == null || !HasselbladStage6Contract.supported(width, height, cfa,
                frames, crop, alreadyProcessed, bayerRgb, neutral)
                || whiteLevel <= 0 || whiteLevel > 65535 || black == null
                || black.length != 4) {
            skipped("unsupported_or_unproven_original_single_bayer_raw");
            return null;
        }
        for (float v : black)
            if (!Float.isFinite(v) || v < 0 || v >= whiteLevel) {
                skipped("invalid_original_raw_levels");
                return null;
            }
        try {
            if (!identity.optBoolean("physical_sensor_proven", false)
                    || !identity.has("physical_sensor_id")
                    || !identity.has("frame_number")
                    || !identity.has("sensor_timestamp_ns")
                    || identity.getInt("width") != width
                    || identity.getInt("height") != height
                    || identity.getInt("cfa") != cfa) {
                skipped("raw_identity_or_geometry_not_matched");
                return null;
            }
            JSONObject j = baseReport("pending");
            j.put("capture", new JSONObject(identity.toString()));
            j.put("output_width", width);
            j.put("output_height", height);
            j.put("original_white_level", whiteLevel);
            j.put("original_black_site_counts", new JSONArray(black));
            j.put("photon_white_point", new JSONArray(neutral));
            j.put("grid","4x4 fixed 8x8 pixel patches, 2-pixel aligned, 1,024 total");
            j.put("pipeline_stage","Bayer2Float/tofloat; output before demosaic/tone mapping");
            j.put("capture_input","single original RAW -> normalized fp16; HDR/stacking excluded");
            j.put("expected_gpu_texture","GL_RGBA16F");
            j.put("value_channel","R output component of the Bayer2Float pixel shader");
            j.put("sample_pixel_coordinates","GPU framebuffer lower-left; RAW-to-GL row orientation not yet proven");
            j.put("cpu_gpu_parity_verified", false);
            j.put("hasselblad_wb_selected",false);
            latest = j.toString();
            return new Session(j, width, height, epoch);
        } catch (Exception ex) {
            skipped("cannot_copy_proven_capture_identity");
            return null;
        }
    }

    private static JSONObject baseReport(String status) {
        JSONObject j = new JSONObject();
        try {
            j.put("schema", "hasselblad-stage6-bayer-gpu-samples-v1");
            j.put("status", status);
            j.put("render_applied", false);
            j.put("automatic_white_balance_calibrated", false);
            j.put("photographic_colour_still_photon", true);
            j.put("full_frame_readback", false);
        } catch (Exception ignored) {}
        return j;
    }

    public static final class Session {
        private final JSONObject document;
        private final int width, height;
        private final long epoch;
        private boolean finished;
        private Session(JSONObject document, int width, int height, long epoch) {
            this.document = document;
            this.width = width;
            this.height = height;
            this.epoch = epoch;
        }
        private void publish() {
            synchronized (HasselbladGpuStageProbe.class) {
                if (epoch == HasselbladGpuStageProbe.epoch)
                    latest = document.toString();
            }
        }
        public void finishIfMissing(String reason) {
            if (finished) return;
            fail(reason);
        }
        private void fail(String reason) {
            finished = true;
            try {
                document.put("status", "skipped");
                document.put("reason", reason);
            } catch (Exception ignored) {}
            publish();
        }

        /** Called immediately after Bayer2Float.drawMain(), before any later
         * render pass rebinds/recycles its framebuffer. Never calls draw.
         * A read format unsupported by the GPU is reported, never fatal to photo.
         */
        public void sample(GLTexture texture, boolean highlightReconstructionEnabled,
                           float highlightClipThreshold, boolean fullUncropped) {
            if (finished) return;
            if (!fullUncropped || texture == null || texture.mSize.x != width
                    || texture.mSize.y != height || texture.mBuffer == 0
                    || texture.mGLFormat != GLES30.GL_RGBA16F) {
                fail("wrong_or_unsupported_bayer_output_texture");
                return;
            }
            final int[] oldFbo={0}, oldPackBuffer={0}, oldAlign={0};
            final int[] oldRowLength={0}, oldSkipRows={0}, oldSkipPixels={0};
            boolean saved = false;
            long start=System.nanoTime();
            try {
                GLES30.glGetIntegerv(GLES30.GL_READ_FRAMEBUFFER_BINDING,oldFbo,0);
                GLES30.glGetIntegerv(GLES30.GL_PIXEL_PACK_BUFFER_BINDING,oldPackBuffer,0);
                GLES30.glGetIntegerv(GLES30.GL_PACK_ALIGNMENT,oldAlign,0);
                GLES30.glGetIntegerv(GLES30.GL_PACK_ROW_LENGTH,oldRowLength,0);
                GLES30.glGetIntegerv(GLES30.GL_PACK_SKIP_ROWS,oldSkipRows,0);
                GLES30.glGetIntegerv(GLES30.GL_PACK_SKIP_PIXELS,oldSkipPixels,0);
                saved=true;
                int prior=GLES30.glGetError();
                if (prior != GLES30.GL_NO_ERROR)
                    throw new IllegalStateException("preexisting_gl_error_" + prior);
                GLES30.glBindFramebuffer(GLES30.GL_READ_FRAMEBUFFER,texture.mBuffer);
                GLES30.glBindBuffer(GLES30.GL_PIXEL_PACK_BUFFER,0);
                GLES30.glPixelStorei(GLES30.GL_PACK_ALIGNMENT,1);
                GLES30.glPixelStorei(GLES30.GL_PACK_ROW_LENGTH,0);
                GLES30.glPixelStorei(GLES30.GL_PACK_SKIP_ROWS,0);
                GLES30.glPixelStorei(GLES30.GL_PACK_SKIP_PIXELS,0);
                if(GLES30.glCheckFramebufferStatus(GLES30.GL_READ_FRAMEBUFFER)
                        != GLES30.GL_FRAMEBUFFER_COMPLETE)
                    throw new IllegalStateException("incomplete_read_framebuffer");
                int glType=GLES30.GL_HALF_FLOAT;
                int bytesPerChannel=2;
                ByteBuffer packed = ByteBuffer.allocateDirect(HasselbladStage6Contract.SAMPLES*4)
                        .order(ByteOrder.LITTLE_ENDIAN);
                JSONArray patches=new JSONArray();
                // First probe: fall back to float32 ONLY if the driver rejects
                // GL_HALF_FLOAT. A different type is labelled, never mistaken
                // for the exact GPU R16F storage bits.
                int[] first=HasselbladStage6Contract.patchRect(width,height,0);
                ByteBuffer tile=ByteBuffer.allocateDirect(8*8*4*4)
                        .order(ByteOrder.LITTLE_ENDIAN);
                tile.clear();
                GLES30.glReadPixels(first[0],first[1],8,8,
                        GLES30.GL_RGBA,glType,tile);
                int glError=GLES30.glGetError();
                if(glError!=GLES30.GL_NO_ERROR) {
                    glType=GLES30.GL_FLOAT;bytesPerChannel=4;
                    tile.clear();
                    GLES30.glReadPixels(first[0],first[1],8,8,
                            GLES30.GL_RGBA,glType,tile);
                    glError=GLES30.glGetError();
                    if(glError!=GLES30.GL_NO_ERROR)
                        throw new IllegalStateException("unsupported_gpu_read_format_"+glError);
                }
                for(int i=0;i<HasselbladStage6Contract.PATCH_COUNT;i++) {
                    int[] rect=HasselbladStage6Contract.patchRect(width,height,i);
                    if(i!=0) {
                        tile.clear();
                        GLES30.glReadPixels(rect[0],rect[1],8,8,GLES30.GL_RGBA,glType,tile);
                        glError=GLES30.glGetError();
                        if(glError!=GLES30.GL_NO_ERROR)
                            throw new IllegalStateException("gpu_read_failed_"+i+"_"+glError);
                    }
                    tile.rewind();
                    for(int v=0;v<64;v++) {
                        if(bytesPerChannel==2)packed.putShort(tile.getShort(v*8));
                        else packed.putFloat(tile.getFloat(v*16));
                    }
                    patches.put(new JSONArray().put(rect[0]).put(rect[1])
                            .put(rect[2]).put(rect[3]));
                }
                int expected=HasselbladStage6Contract.SAMPLES*bytesPerChannel;
                if(packed.position()!=expected)
                    throw new IllegalStateException("short_gpu_read_result");
                byte[] out=new byte[expected];
                packed.flip();packed.get(out);
                document.put("patches_xywh",patches);
                document.put("sample_encoding",bytesPerChannel==2?
                        "base64-little-endian-r16f":"base64-little-endian-r32f");
                document.put("samples_r_base64",Base64.encodeToString(out,Base64.NO_WRAP));
                document.put("samples_count",HasselbladStage6Contract.SAMPLES);
                document.put("readback_bytes",out.length);
                document.put("fp16_source_texture",true);
                document.put("highlight_reconstruction_enabled",highlightReconstructionEnabled);
                document.put("highlight_clip_threshold",highlightClipThreshold);
                document.put("exposure_headroom_note",
                        "Values above unity and negatives retained, not gamma/tone encoded; "
                        +"HLRECON paths require separate CPU eligibility.");
                document.put("elapsed_ms",(System.nanoTime()-start)/1e6);
                document.put("status","completed");
                finished=true;
                publish();
            } catch (Exception | OutOfMemoryError error) {
                fail("readback_unavailable_"+error.getClass().getSimpleName()
                        +(error.getMessage()==null?"":"_"+error.getMessage()));
            } finally {
                if(saved) {
                    try {
                        GLES30.glBindFramebuffer(GLES30.GL_READ_FRAMEBUFFER,oldFbo[0]);
                        GLES30.glBindBuffer(GLES30.GL_PIXEL_PACK_BUFFER,oldPackBuffer[0]);
                        GLES30.glPixelStorei(GLES30.GL_PACK_ALIGNMENT,oldAlign[0]);
                        GLES30.glPixelStorei(GLES30.GL_PACK_ROW_LENGTH,oldRowLength[0]);
                        GLES30.glPixelStorei(GLES30.GL_PACK_SKIP_ROWS,oldSkipRows[0]);
                        GLES30.glPixelStorei(GLES30.GL_PACK_SKIP_PIXELS,oldSkipPixels[0]);
                    } catch (Exception ignored) {
                        // Never hide the original render error or rerender.
                    }
                }
            }
        }
    }
}
