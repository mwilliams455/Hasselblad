import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;
public final class Stage58Check {
 static long checks;static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
 static byte[] shorts(short[] a){var b=ByteBuffer.allocate(a.length*2).order(ByteOrder.LITTLE_ENDIAN);for(short v:a)b.putShort(v);return b.array();}
 static byte[] floats(float[] a){var b=ByteBuffer.allocate(a.length*4).order(ByteOrder.LITTLE_ENDIAN);for(float v:a)b.putFloat(v);return b.array();}
 static byte[] longs(long[] a){var b=ByteBuffer.allocate(a.length*8).order(ByteOrder.LITTLE_ENDIAN);for(long v:a)b.putLong(v);return b.array();}
 public static void main(String[] args)throws Exception {
  Path root=Path.of(args[0]);long channels=0;
  for(int i=0;i<12;i++)for(int limit:new int[]{4096,512,256,1}) {
   String name="case"+i;var p=HasselbladDngTileReader.readPreviewWithPreparation58(root.resolve(name+".dng").toFile(),limit);var a=p.preparation58;
   Path prefix=root.resolve(name+"-"+limit);
   check(Arrays.equals(shorts(p.cameraRgb16),Files.readAllBytes(Path.of(prefix+".legacy"))),"legacy reference "+prefix);
   check(Arrays.equals(shorts(a.rgb16),Files.readAllBytes(Path.of(prefix+".rgb16"))),"range reference "+prefix);
   check(Arrays.equals(floats(a.unclampedRgb),Files.readAllBytes(Path.of(prefix+".unclamped"))),"float diagnostic "+prefix);
   check(Arrays.equals(longs(a.counters()),Files.readAllBytes(Path.of(prefix+".counters"))),"counter reference "+prefix);
   var old=HasselbladDngTileReader.readPreview(root.resolve(name+".dng").toFile(),limit);
   check(old.preparation58==null&&Arrays.equals(old.cameraRgb16,p.cameraRgb16),"legacy preserved");
   check(a.decodedSites<=64*64&&a.decodedSites>0,"unique row bound");
   if(i%4==0)check(a.gainClipEvents==0,"absent map");
   channels+=a.rgb16.length;
  }
  for(String bad:new String[]{"compressed","bad_cfa","crop","dual","opcode","black_repeat","linearization","layout","strip"}) {
   boolean rejected=false;try{HasselbladDngTileReader.readPreviewWithPreparation58(Path.of(args[1]).resolve("bad_"+bad+".dng").toFile(),4096);}catch(IOException e){rejected=true;}
   check(rejected,"reject "+bad);
  }
  boolean cancelled=false;Thread.currentThread().interrupt();try{HasselbladDngTileReader.readPreviewWithPreparation58(root.resolve("case0.dng").toFile(),4096);}catch(IOException e){cancelled=true;}finally{Thread.interrupted();}
  check(cancelled,"cancel");
  System.out.println("{\"status\":\"PASS\",\"checks\":"+checks+",\"cases\":48,\"rgb_channels\":"+channels+",\"raw_preparation_exact_numpy\":true,\"diagnostic_float_exact_numpy\":true,\"legacy_preview_unchanged_exact\":true,\"sdk_bit_exact_claimed\":false}");
 }
}
