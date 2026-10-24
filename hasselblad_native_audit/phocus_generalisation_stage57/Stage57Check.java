import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;

/** Executes the app's existing Java/JNI chain on explicit synthetic encodings. */
public final class Stage57Check {
    static double[] doubles(ByteBuffer b,int n){double[] a=new double[n];for(int i=0;i<n;i++)a[i]=b.getDouble();return a;}
    static void save(Path p,short[] a)throws Exception {
        var b=ByteBuffer.allocate(a.length*2).order(ByteOrder.LITTLE_ENDIAN);for(short v:a)b.putShort(v);Files.write(p,b.array());
    }
    static void save(Path p,double[] a)throws Exception {
        var b=ByteBuffer.allocate(a.length*8).order(ByteOrder.LITTLE_ENDIAN);for(double v:a)b.putDouble(v);Files.write(p,b.array());
    }
    public static void main(String[] args)throws Exception {
        Path fixtures=Path.of(args[0]),out=Path.of(args[2]);Files.createDirectories(out);
        HasselbladProfile43 look;try(var in=new FileInputStream(args[1])){look=HasselbladProfile43.read(in);}
        var b=ByteBuffer.wrap(Files.readAllBytes(fixtures.resolve("cases.bin"))).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic=new byte[8];b.get(magic);if(!Arrays.equals(magic,"HB57TEST".getBytes()))throw new AssertionError("Magic");
        int cases=b.getInt(),pixels=b.getInt();double maxK=0,maxMatrix=0;StringBuilder rows=new StringBuilder();
        for(int caseIndex=0;caseIndex<cases;caseIndex++) {
            int id=b.getInt(),nominal=b.getInt(),encoding=b.getInt();double expectedK=b.getDouble();int expectedLut=b.getInt();
            double[] cm=doubles(b,9),fm=doubles(b,9),n=doubles(b,3),expectedMatrix=doubles(b,9);
            short[] raw=new short[pixels*3];for(int i=0;i<raw.length;i++)raw[i]=b.getShort();short[] before=raw.clone();
            var selected=HasselbladIlluminant56.estimate(cm,null,0,0,null,null,null,n);
            maxK=Math.max(maxK,Math.abs(selected.kelvin-expectedK));
            if(Math.abs(selected.kelvin-expectedK)>1e-5||selected.lutKelvin!=expectedLut)throw new AssertionError("Selection");
            double[] matrix=HasselbladRenderer42.cameraToD50(fm,fm,null,null,null,n);
            for(int i=0;i<9;i++)maxMatrix=Math.max(maxMatrix,Math.abs(matrix[i]-expectedMatrix[i]));
            var plan=HasselbladPreparedHighlight54.prepare(matrix,n);
            double[] grid=look.gridAtTemperature(selected.lutKelvin),plainParams=look.parameters(matrix),params=look.parameters(plan.afterMatrix);
            short[] plain=HasselbladRenderer42.render(raw,plainParams,grid,look.curve,look.gridWidth,look.gridHeight,1);
            short[] prepared=plan.reconstruct(raw);
            short[] highlighted=HasselbladRenderer42.render(prepared,params,grid,look.curve,look.gridWidth,look.gridHeight,1);
            short[] plainFinished=look.finishRgb16(plain),highlightedFinished=look.finishRgb16(highlighted);
            if(!Arrays.equals(raw,before))throw new AssertionError("Input changed");
            Path folder=out.resolve(String.format(java.util.Locale.ROOT,"case_%03d",id));Files.createDirectories(folder);
            save(folder.resolve("raw.bin"),raw);save(folder.resolve("plain_colour.bin"),plain);save(folder.resolve("highlight_input.bin"),prepared);
            save(folder.resolve("highlight_colour.bin"),highlighted);save(folder.resolve("plain_finished.bin"),plainFinished);save(folder.resolve("highlight_finished.bin"),highlightedFinished);
            save(folder.resolve("camera_to_d50.bin"),matrix);save(folder.resolve("after_matrix.bin"),plan.afterMatrix);
            save(folder.resolve("plain_params.bin"),plainParams);save(folder.resolve("highlight_params.bin"),params);
            rows.append("{\"id\":").append(id).append(",\"metadata_kelvin\":").append(selected.kelvin)
                .append(",\"lut_kelvin\":").append(selected.lutKelvin).append(",\"analytic_equal_gain_limit\":")
                .append(plan.analyticEqualGainLimit).append("}\n");
        }
        if(b.hasRemaining()||maxMatrix>1e-12)throw new AssertionError("Fixture/matrix");
        Files.writeString(out.resolve("HOST_CASES57.jsonl"),rows.toString());
        String receipt="{\"schema\":\"hasselblad-stage57-host-execution-v1\",\"status\":\"PASS_EXECUTION_ONLY\",\"cases\":"+cases+
            ",\"pixels_per_case\":"+pixels+",\"metadata_kelvin_max_error\":"+maxK+",\"camera_matrix_max_error\":"+maxMatrix+
            ",\"inputs_unchanged\":true,\"renderer_code_changed\":false,\"device_tested\":false}";
        Files.writeString(out.resolve("HOST_EXECUTION57.json"),receipt+"\n");System.out.println(receipt);
    }
}
