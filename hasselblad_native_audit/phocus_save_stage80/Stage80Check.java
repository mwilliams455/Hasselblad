import com.particlesdevs.photoncamera.hasselblad.HasselbladPublication80;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class Stage80Check {
    static void check(boolean ok,String reason){if(!ok)throw new AssertionError(reason);}
    static final class Store implements HasselbladPublication80.Store {
        Map<String,Doc> files=new HashMap<>();String mode="ok",mime;int creates,queries;String finalName="photo.jpg";
        public boolean exists(String name){if(mode.equals("race")&&++queries==2)files.put(name,new Doc(this,name));return files.containsKey(name);}
        public HasselbladPublication80.Document create(String mime,String name)throws IOException {
            check(!name.endsWith(".tmp"),"Scoped storage forbids generic temporary files");
            check(name.endsWith(finalName.endsWith(".jpg")?".jpg":".dng"),"Wrong media suffix");
            this.mime=mime;creates++;
            if(mode.equals("create"))throw new IOException("injected create failure");
            Doc doc=new Doc(this,name);files.put(name,doc);return doc;
        }
    }
    static final class Doc implements HasselbladPublication80.Document {
        Store store;String name;ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        Doc(Store store,String name){this.store=store;this.name=name;}
        public OutputStream open()throws IOException {
            if(store.mode.equals("open"))throw new IOException("injected open failure");
            return new OutputStream(){
                public void write(int b)throws IOException{bytes.write(b);}
                public void write(byte[] b,int off,int n)throws IOException {
                    if(store.mode.equals("write")||store.mode.equals("cleanup"))throw new IOException("injected write failure");
                    bytes.write(b,off,n);if(store.mode.equals("cancel"))Thread.currentThread().interrupt();
                }
                public void close()throws IOException{if(store.mode.equals("close"))throw new IOException("injected close failure");}
            };
        }
        public long length(){return bytes.size()+(store.mode.equals("short")?-1:0);}
        public String name(){return name;}
        public boolean rename(String requested) {
            if(store.mode.equals("rename")||store.files.containsKey(requested))return false;
            store.files.remove(name);name=store.mode.equals("renamed_elsewhere")?"changed.jpg":requested;store.files.put(name,this);return true;
        }
        public boolean delete(){if(store.mode.equals("cleanup"))return false;store.files.remove(name);return true;}
    }
    public static void main(String[] args)throws Exception {
        Path work=Path.of(args[0]);Path source=work.resolve("synthetic80.bin");
        byte[] payload=new byte[200003];new Random(80).nextBytes(payload);Files.write(source,payload);
        int cases=0;
        for(String name:new String[]{"photo.jpg","photo.dng"}) {
            Store s=new Store();s.finalName=name;HasselbladPublication80.publish(source,name,s);
            check(s.files.size()==1&&Arrays.equals(payload,s.files.get(name).bytes.toByteArray()),"Saved bytes differ");
            check(s.mime.equals(name.endsWith(".jpg")?"image/jpeg":"image/x-adobe-dng"),"MIME incorrect");cases++;
        }
        for(String mode:new String[]{"create","open","write","close","short","rename","renamed_elsewhere","cancel","race","cleanup"}) {
            Store s=new Store();s.mode=mode;IOException failure=null;
            try{HasselbladPublication80.publish(source,"photo.jpg",s);}catch(IOException e){failure=e;}finally{Thread.interrupted();}
            check(failure!=null,"Injected failure accepted: "+mode);
            if(mode.equals("race"))check(s.files.size()==1&&s.files.containsKey("photo.jpg")&&s.files.get("photo.jpg").bytes.size()==0,"Collision modified existing image");
            else if(mode.equals("cleanup"))check(failure.getSuppressed().length==1,"Cleanup error masked or lost");
            else check(s.files.isEmpty(),"Incomplete public document remains: "+mode);
            check(Arrays.equals(payload,Files.readAllBytes(source)),"Private render was changed");cases++;
        }
        Store collision=new Store();Doc existing=new Doc(collision,"photo.jpg");existing.bytes.write(42);collision.files.put("photo.jpg",existing);
        boolean rejected=false;try{HasselbladPublication80.publish(source,"photo.jpg",collision);}catch(FileAlreadyExistsException e){rejected=true;}
        check(rejected&&collision.creates==0&&existing.bytes.toByteArray()[0]==42,"Existing photo overwritten");cases++;
        for(String name:new String[]{"../photo.jpg","photo.tmp","","x\\photo.dng"}) {
            rejected=false;try{HasselbladPublication80.publish(source,name,new Store());}catch(IOException e){rejected=true;}
            check(rejected,"Invalid public filename accepted");cases++;
        }
        Store cancelled=new Store();Thread.currentThread().interrupt();rejected=false;
        try{HasselbladPublication80.publish(source,"photo.jpg",cancelled);}catch(IOException e){rejected=true;}finally{Thread.interrupted();}
        check(rejected&&cancelled.creates==0,"Pre-cancelled capture created a document");cases++;
        Files.writeString(work.resolve("STAGE80_HOST_VALIDATION.json"),"{\"schema\":\"hasselblad-stage80-host-v1\",\"status\":\"PASS_PUBLICATION\",\"publication_cases\":"+cases+",\"private_source_unchanged\":true,\"android_storage_device_tested\":false}\n");
        System.out.println("STAGE80_PUBLICATION_PASS "+cases+" cases; image MIME/extensions, exact bytes, collision, cancellation, injected provider failures and cleanup");
    }
}
