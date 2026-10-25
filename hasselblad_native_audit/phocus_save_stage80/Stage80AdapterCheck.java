import com.particlesdevs.photoncamera.hasselblad.HasselbladCaptureFiles80;
import android.content.*;
import android.net.Uri;
import androidx.documentfile.provider.DocumentFile;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class Stage80AdapterCheck {
    static void check(boolean ok,String reason){if(!ok)throw new AssertionError(reason);}
    static Uri grant(Context c,String authority,String id,boolean read,boolean write) {
        Uri uri=new Uri(authority,id,true);c.resolver.grants.add(new UriPermission(uri,read,write));
        DocumentFile.ROOTS.put(uri,new DocumentFile("grant",true));return uri;
    }
    public static void main(String[] args)throws Exception {
        String authority="com.android.externalstorage.documents";int cases=0;
        Path source=Path.of(args[0],"adapter80-image.bin");byte[] payload={1,5,12,64,0,-1};Files.write(source,payload);
        for(String ext:new String[]{"jpg","dng"}) {
            Context c=new Context();Uri uri=grant(c,authority,"primary:DCIM",true,true);
            Path target=Path.of("/hb80-primary/DCIM/HasselbladPhoton/Raw/test."+ext);
            HasselbladCaptureFiles80.publish(c,source,target);
            var file=DocumentFile.ROOTS.get(uri).findFile("HasselbladPhoton").findFile("Raw").findFile("test."+ext);
            check(Arrays.equals(payload,file.bytes.toByteArray()),"Actual adapter copied different bytes");
            check(file.mime.equals(ext.equals("jpg")?"image/jpeg":"image/x-adobe-dng"),"Adapter MIME");
            check(c.resolver.opened.size()==1&&c.resolver.opened.get(0)!=file.getUri(),"Updated rename URI not retained");cases++;
        }
        Context root=new Context();Uri whole=grant(root,authority,"primary:",true,true);
        HasselbladCaptureFiles80.publish(root,source,Path.of("/hb80-primary/DCIM/Camera/root.jpg"));
        check(DocumentFile.ROOTS.get(whole).findFile("DCIM").findFile("Camera").findFile("root.jpg")!=null,"Primary root grant");cases++;
        Uri narrower=grant(root,authority,"primary:DCIM/Camera",true,true);
        HasselbladCaptureFiles80.publish(root,source,Path.of("/hb80-primary/DCIM/Camera/narrow.jpg"));
        check(DocumentFile.selected==narrower,"Most specific matching grant ignored");cases++;
        Object[][] invalid={
            {authority,"primary:Pictures",true,true,"/hb80-primary/DCIM/Camera/x.jpg"},
            {authority,"primary:DCIM",true,false,"/hb80-primary/DCIM/Camera/x.jpg"},
            {authority,"1234:DCIM",true,true,"/hb80-primary/DCIM/Camera/x.jpg"},
            {authority,"primary:DCIM",true,true,"/hb80-primary-other/DCIM/Camera/x.jpg"},
            {authority,"primary:DCIM",true,true,"/hb80-primary/../outside/DCIM/x.jpg"},
            {authority,"primary:",true,true,"/hb80-primary/Movies/x.jpg"},
            {"remote.provider","primary:DCIM",true,true,"/hb80-primary/DCIM/Camera/x.jpg"},
            {authority,"primary:DCIMX",true,true,"/hb80-primary/DCIM/Camera/x.jpg"}
        };
        for(Object[] test:invalid) {
            Context c=new Context();Uri uri=grant(c,(String)test[0],(String)test[1],(Boolean)test[2],(Boolean)test[3]);
            boolean failed=false;try{HasselbladCaptureFiles80.publish(c,source,Path.of((String)test[4]));}catch(IOException e){failed=true;}
            check(failed&&c.resolver.opened.isEmpty()&&DocumentFile.ROOTS.get(uri).children.isEmpty(),"Invalid grant/path caused public write");cases++;
        }
        System.out.println("STAGE80_ADAPTER_PASS "+cases);
    }
}
