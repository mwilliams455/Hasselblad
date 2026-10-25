import com.particlesdevs.photoncamera.hasselblad.HasselbladCaptureFiles80;
import android.content.*;
import android.net.Uri;
import androidx.documentfile.provider.DocumentFile;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class Stage82AdapterCheck {
    static void check(boolean ok,String reason){Stage80AdapterCheck.check(ok,reason);}
    static final String AUTHORITY="com.android.externalstorage.documents";
    static DocumentFile folder(Context c,String relative){
        Uri grant=Stage80AdapterCheck.grant(c,AUTHORITY,"primary:"+relative,true,true);
        return DocumentFile.fromTreeUri(c,grant);
    }
    public static void main(String[] args)throws Exception {
        Stage80AdapterCheck.main(args);int cases=12;
        Path source=Path.of(args[0],"adapter82-image.bin"),target=Path.of("/hb80-primary/DCIM/Camera/target.jpg");
        byte[] bytes=new byte[200003];new Random(82).nextBytes(bytes);Files.write(source,bytes);
        for(int siblings:new int[]{0,1,10000}) {
            Context c=new Context();DocumentFile folder=folder(c,"DCIM/Camera");
            for(int i=0;i<siblings;i++)folder.createFile("image/jpeg","old-"+i+".jpg").bytes.write(42);
            DocumentFile.nameReads=0;var metrics=new HasselbladCaptureFiles80.Metrics();
            HasselbladCaptureFiles80.publish(c,source,target,metrics);
            check(c.resolver.targetQueries==2&&c.resolver.parentProbes==2&&c.resolver.bulkQueries==0,"Lookup cost grew with folder size");
            check(c.resolver.queried.size()==4&&DocumentFile.nameReads==1,"Unexpected provider calls");
            check(((Number)metrics.snapshot().get("name_check_rows")).intValue()==0,"Unrelated filename rows scanned");
            check(((Number)metrics.snapshot().get("name_lookup_missing_target_exceptions")).intValue()==2,"AOSP missing-child exception not handled");
            check(folder.children.size()==siblings+1&&Arrays.equals(bytes,folder.findFile("target.jpg").bytes.toByteArray()),"Copied bytes differ");
            for(var entry:folder.children.entrySet())if(entry.getKey().startsWith("old-"))check(entry.getValue().bytes.toByteArray()[0]==42,"Existing file changed");
            check(c.resolver.closedCursors==c.resolver.openedCursors,"Cursor leak");cases++;
        }
        for(String missing:new String[]{"target_empty","target_null"}) {
            Context c=new Context();DocumentFile folder=folder(c,"DCIM/Camera");c.resolver.mode=missing;
            HasselbladCaptureFiles80.publish(c,source,target);
            check(c.resolver.targetQueries==2&&c.resolver.parentProbes==2&&folder.findFile("target.jpg")!=null,"Missing document behavior rejected");
            check(c.resolver.closedCursors==c.resolver.openedCursors,"Missing lookup cursor leak");cases++;
        }
        for(String filename:new String[]{"space #100%.jpg","colours-青.dng"}) {
            Context c=new Context();DocumentFile folder=folder(c,"DCIM/My Photos");
            HasselbladCaptureFiles80.publish(c,source,Path.of("/hb80-primary/DCIM/My Photos",filename));
            check(c.resolver.targetQueries==2&&c.resolver.bulkQueries==0,"Special filename fell back to scan");
            check(c.resolver.queried.get(0).id.equals("primary:DCIM/My Photos/"+filename),"Child identifier changed literal filename");
            check(Arrays.equals(bytes,folder.findFile(filename).bytes.toByteArray()),"Special filename bytes differ");cases++;
        }
        Context fallback=new Context();fallback.resolver.opaqueFolder=true;DocumentFile unknown=folder(fallback,"DCIM/Camera");
        unknown.createFile("image/jpeg","keep.jpg").bytes.write(42);
        HasselbladCaptureFiles80.publish(fallback,source,target);
        check(fallback.resolver.bulkQueries==2&&fallback.resolver.targetQueries==0&&fallback.resolver.parentProbes==0,"Guessed opaque child identifier");
        check(unknown.findFile("keep.jpg").bytes.toByteArray()[0]==42&&Arrays.equals(bytes,unknown.findFile("target.jpg").bytes.toByteArray()),"Fallback changed images");cases++;
        for(String mode:new String[]{"target_argument","target_missing_other_id"}) {
            Context c=new Context();DocumentFile folder=folder(c,"DCIM/Camera");c.resolver.mode=mode;
            var metrics=new HasselbladCaptureFiles80.Metrics();HasselbladCaptureFiles80.publish(c,source,target,metrics);
            check(c.resolver.bulkQueries==2&&c.resolver.targetQueries==2&&c.resolver.parentProbes==0,"Unknown target error did not use bulk fallback");
            check(((Number)metrics.snapshot().get("name_lookup_missing_target_exceptions")).intValue()==0,"Unrelated missing-file error accepted as target absence");
            check(((Number)metrics.snapshot().get("name_lookup_query_fallbacks")).intValue()==2,"Query fallback not recorded");
            check(Arrays.equals(bytes,folder.findFile("target.jpg").bytes.toByteArray()),"Query fallback bytes differ");cases++;
        }
        String[] failures={"target_permission","second_target_permission","target_wrong_id","target_duplicate","target_unnamed","target_column","target_cursor","target_loading","target_error","target_cancel",
            "parent_permission","parent_null","parent_empty","parent_wrong_id","parent_not_directory","parent_duplicate","parent_column","parent_cursor","parent_loading","parent_error","parent_cancel",
            "collision","race","target_null_existing","target_argument_existing","bulk_null","bulk_permission","bulk_column","bulk_cursor","bulk_loading","bulk_error","bulk_unnamed"};
        for(String mode:failures) {
            Context c=new Context();c.resolver.opaqueFolder=mode.startsWith("bulk_");DocumentFile folder=folder(c,"DCIM/Camera");
            folder.createFile("image/jpeg","keep.jpg").bytes.write(42);
            boolean existing=mode.equals("collision")||mode.equals("target_null_existing")||mode.equals("target_argument_existing");
            if(existing)folder.createFile("image/jpeg","target.jpg").bytes.write(42);
            c.resolver.mode=mode.equals("target_null_existing")?"target_null":mode.equals("target_argument_existing")?"target_argument":mode;
            var metrics=new HasselbladCaptureFiles80.Metrics();boolean failed=false;
            try{HasselbladCaptureFiles80.publish(c,source,target,metrics);}catch(IOException|RuntimeException e){failed=true;}finally{Thread.interrupted();}
            check(failed,"Invalid lookup accepted: "+mode);
            existing|=mode.equals("race");
            check(folder.children.size()==(existing?2:1)&&folder.findFile("keep.jpg").bytes.toByteArray()[0]==42,"Failure damaged files or leaked temporary: "+mode);
            if(existing)check(folder.findFile("target.jpg").bytes.toByteArray()[0]==42,"Existing destination overwritten: "+mode);
            check(c.resolver.closedCursors==c.resolver.openedCursors,"Failure leaked cursor: "+mode);
            check(metrics.snapshot().containsKey("name_check_milliseconds"),"Failure timing lost: "+mode);
            if(mode.equals("second_target_permission")||mode.equals("race")||mode.equals("target_null_existing"))
                check(metrics.snapshot().containsKey("cleanup_milliseconds"),"Cleanup timing lost: "+mode);
            else check(c.resolver.opened.isEmpty(),"Wrote after invalid initial lookup: "+mode);
            check(Arrays.equals(bytes,Files.readAllBytes(source)),"Private source changed");cases++;
        }
        System.out.println("STAGE82_ADAPTER_PASS "+cases);
    }
}
