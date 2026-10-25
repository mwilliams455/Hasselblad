import com.particlesdevs.photoncamera.hasselblad.HasselbladCaptureFiles80;
import android.content.*;
import android.net.Uri;
import androidx.documentfile.provider.DocumentFile;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class Stage81AdapterCheck {
    static void check(boolean ok,String message){Stage80AdapterCheck.check(ok,message);}
    static final String AUTHORITY="com.android.externalstorage.documents";
    static DocumentFile folder(Context context){
        Uri uri=Stage80AdapterCheck.grant(context,AUTHORITY,"primary:DCIM/Camera",true,true);
        return DocumentFile.ROOTS.get(uri);
    }
    public static void main(String[] args)throws Exception {
        Stage80AdapterCheck.main(args);int cases=12;
        Path source=Path.of(args[0],"adapter81-image.bin"),target=Path.of("/hb80-primary/DCIM/Camera/target.jpg");
        byte[] payload=new byte[200003];new Random(81).nextBytes(payload);Files.write(source,payload);
        for(int count:new int[]{0,1,10000}) {
            Context c=new Context();DocumentFile folder=folder(c);
            for(int i=0;i<count;i++)folder.createFile("image/jpeg","old-"+i+".jpg").bytes.write(42);
            DocumentFile.nameReads=0;
            var metrics=new HasselbladCaptureFiles80.Metrics();
            HasselbladCaptureFiles80.publish(c,source,target,metrics);
            var snapshot=metrics.snapshot();
            check(c.resolver.queries==2&&c.resolver.closedCursors==2,"Filename queries must stay at two for any folder size");
            check(DocumentFile.nameReads==1,"Per-child name queries returned");
            check(((Number)snapshot.get("name_check_rows")).longValue()==2L*count+1,"Incomplete filename scan");
            check(((Number)snapshot.get("name_check_calls")).intValue()==2,"Missing collision metrics");
            for(String phase:new String[]{"folder_lookup","name_check","create","open","write","close","length","rename","final_name"})
                check(snapshot.containsKey(phase+"_milliseconds")&&((Number)snapshot.get(phase+"_milliseconds")).doubleValue()>=0,"Missing timing: "+phase);
            check(((Number)snapshot.get("write_calls")).intValue()==4,"Writes must remain buffered");
            check(folder.children.size()==count+1&&Arrays.equals(payload,folder.findFile("target.jpg").bytes.toByteArray()),"Wrong saved bytes or changed siblings");
            for(var entry:folder.children.entrySet())if(entry.getKey().startsWith("old-"))check(entry.getValue().bytes.size()==1,"Existing file changed");
            cases++;
        }
        for(String mode:new String[]{"null","column","cursor","unnamed","loading","cancel","first_query","second_query","collision","race"}) {
            Context c=new Context();DocumentFile folder=folder(c);folder.createFile("image/jpeg","keep.jpg").bytes.write(42);
            c.resolver.queryMode=mode;c.resolver.loading=mode.equals("loading");
            if(mode.equals("first_query"))c.resolver.queryFailureAt=1;
            if(mode.equals("second_query"))c.resolver.queryFailureAt=2;
            if(mode.equals("collision"))folder.createFile("image/jpeg","target.jpg").bytes.write(42);
            var metrics=new HasselbladCaptureFiles80.Metrics();boolean failed=false;
            try{HasselbladCaptureFiles80.publish(c,source,target,metrics);}catch(IOException|RuntimeException e){failed=true;}finally{Thread.interrupted();}
            check(failed,"Incomplete/failed query accepted: "+mode);
            boolean collision=mode.equals("collision")||mode.equals("race");
            check(folder.children.size()==(collision?2:1)&&folder.findFile("keep.jpg").bytes.toByteArray()[0]==42,"Failed save damaged siblings or leaked temporary: "+mode);
            if(collision)check(folder.findFile("target.jpg").bytes.toByteArray()[0]==42,"Collision overwritten");
            int cursorCount=c.resolver.queries-(mode.equals("null")||mode.endsWith("_query")?1:0);
            check(c.resolver.closedCursors==cursorCount,"Cursor leaked: "+mode);
            check(metrics.snapshot().containsKey("name_check_milliseconds"),"Failed lookup timing lost");
            if(mode.equals("second_query")||mode.equals("race"))check(metrics.snapshot().containsKey("cleanup_milliseconds"),"Cleanup timing lost");
            else check(c.resolver.opened.isEmpty(),"Failure before creation wrote a document");
            check(Arrays.equals(payload,Files.readAllBytes(source)),"Private input modified");cases++;
        }
        System.out.println("STAGE81_ADAPTER_PASS "+cases);
    }
}
