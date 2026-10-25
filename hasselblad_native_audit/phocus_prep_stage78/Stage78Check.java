import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class Stage78Check {
    static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static long compare(File path)throws Exception {
        var before=Files.readAllBytes(path.toPath());
        var a=HasselbladDngTileReader.readPrepared76(path);var b=HasselbladDngTileReader.readPrepared78(path).frame;
        check(HasselbladDngTileReader.validatePrepared78(path,b)==49152,"Reference sample check count");
        check(Arrays.equals(a.bayer,b.bayer),"Prepared Bayer differs: "+path.getName());
        check(a.belowBlack==b.belowBlack&&a.atWhite==b.atWhite&&a.gainClips==b.gainClips,"Clipping counters differ");
        check(a.orientation==b.orientation&&a.metadata.gainAppliedSamples==b.metadata.gainAppliedSamples,"Application counters differ");
        check(Arrays.equals(a.metadata.forwardMatrix1,b.metadata.forwardMatrix1)&&Arrays.equals(a.metadata.asShotNeutral,b.metadata.asShotNeutral),"Metadata differs");
        check(Arrays.equals(before,Files.readAllBytes(path.toPath())),"Source DNG changed");return a.bayer.length;
    }
    public static void main(String[] args)throws Exception {
        Path fixtures=Path.of(args[0]);long sites=0;
        for(int i=0;i<4;i++)sites+=compare(fixtures.resolve("case"+i+".dng").toFile());
        for(int i=0;i<10;i++)sites+=compare(fixtures.resolve("prep78-"+i+".dng").toFile());
        for(String name:new String[]{"bad_cfa","compressed","crop","short_file","small","opcode","dual","white"}) {
            boolean rejected=false;try{HasselbladDngTileReader.readPrepared78(fixtures.resolve(name+".dng").toFile());}catch(IOException e){rejected=true;}
            check(rejected,"Malformed DNG accepted: "+name);
        }
        Thread.currentThread().interrupt();boolean cancelled=false;
        try{HasselbladDngTileReader.readPrepared78(fixtures.resolve("case0.dng").toFile());}catch(IOException e){cancelled=true;}finally{Thread.interrupted();}
        check(cancelled,"Preparation cancellation ignored");
        File large=fixtures.resolve("prep78-large.dng").toFile();long t=System.nanoTime();
        var old=HasselbladDngTileReader.readPrepared76(large);double original=(System.nanoTime()-t)/1e6;t=System.nanoTime();
        var fast=HasselbladDngTileReader.readPrepared78(large);double optimized=(System.nanoTime()-t)/1e6;
        check(Arrays.equals(old.bayer,fast.frame.bayer),"Full 12MP preparation mismatch");
        check(old.belowBlack==fast.frame.belowBlack&&old.atWhite==fast.frame.atWhite&&old.gainClips==fast.frame.gainClips&&old.metadata.gainAppliedSamples==fast.frame.metadata.gainAppliedSamples,"12MP counters differ");
        String report="{\"schema\":\"hasselblad-stage78-host-v1\",\"status\":\"PASS_EXACT_PREPARATION\",\"fixture_bayer_sites_exact\":"+sites+
            ",\"full_scene_bayer_sites_exact\":"+old.bayer.length+",\"stage76_host_ms\":"+original+",\"stage78_host_ms\":"+optimized+
            ",\"host_speedup\":"+(original/optimized)+",\"cache_plan_ms\":"+(fast.cachePlanNanoseconds/1e6)+",\"row_read_ms\":"+(fast.rowReadNanoseconds/1e6)+
            ",\"pixel_preparation_ms\":"+(fast.pixelPreparationNanoseconds/1e6)+",\"clipping_and_application_counters_exact\":true,\"phone_speed_measured\":false}";
        Files.writeString(Path.of(args[1]),report+"\n");System.out.println(report);
        System.out.println("STAGE78_PREPARATION_EXACT; malformed inputs, source immutability and cancellation PASS");
    }
}
