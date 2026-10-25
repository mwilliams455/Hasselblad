package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.content.UriPermission;
import android.database.Cursor;
import android.net.Uri;
import android.os.Environment;
import android.provider.DocumentsContract;
import androidx.documentfile.provider.DocumentFile;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Supplier;

/** Uses the already granted primary-DCIM tree; never creates a public .tmp via FUSE. */
public final class HasselbladCaptureFiles80 {
    private HasselbladCaptureFiles80() {}
    /** Per-publication diagnostics; contains durations/counts only, never paths or filenames. */
    public static final class Metrics {
        private final Map<String,Long> nanos=new LinkedHashMap<>();
        private final Map<String,Integer> calls=new LinkedHashMap<>();
        private long rows;
        private void add(String phase,long start) {
            nanos.merge(phase,System.nanoTime()-start,Long::sum);
            calls.merge(phase,1,Integer::sum);
        }
        public Map<String,Object> snapshot() {
            Map<String,Object> result=new LinkedHashMap<>();
            for(String phase:nanos.keySet()) {
                result.put(phase+"_milliseconds",nanos.get(phase)/1e6);
                result.put(phase+"_calls",calls.get(phase));
            }
            result.put("name_check_rows",rows);
            return result;
        }
    }
    private interface IOAction<T> {T run() throws IOException;}
    private static <T> T timedIO(Metrics m,String phase,IOAction<T> action)throws IOException {
        long start=System.nanoTime();try{return action.run();}finally{m.add(phase,start);}
    }
    private static <T> T timed(Metrics m,String phase,Supplier<T> action) {
        long start=System.nanoTime();try{return action.get();}finally{m.add(phase,start);}
    }
    private static boolean exists(Context context,DocumentFile folder,String name,Metrics m)throws IOException {
        // DocumentFile.findFile lists IDs, then queries every child's name separately.
        // Fetch all names in one cursor; keep the two independent collision checks.
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(folder.getUri(),
                DocumentsContract.getDocumentId(folder.getUri()));
        try(Cursor cursor=context.getContentResolver().query(children,
                new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)) {
            if(cursor==null)throw new IOException("Capture filename query returned no result");
            int column=cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            while(cursor.moveToNext()) {
                if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
                m.rows++;
                String found=cursor.getString(column);
                if(found==null)throw new IOException("Capture filename query returned an unnamed document");
                if(name.equals(found))return true;
            }
            if(cursor.getExtras().getBoolean(DocumentsContract.EXTRA_LOADING,false))
                throw new IOException("Capture filename query is incomplete");
            return false;
        }
    }
    private static DocumentFile parent(Context context,Path destination) throws IOException {
        File target=destination.toFile().getCanonicalFile();
        String root=Environment.getExternalStorageDirectory().getCanonicalPath();
        String absolute=target.getParent();
        if(absolute==null || !absolute.startsWith(root+File.separator))
            throw new IOException("Capture destination is outside primary storage");
        String relative=absolute.substring(root.length()+1);
        if(!relative.equals("DCIM") && !relative.startsWith("DCIM/"))
            throw new IOException("Capture destination is outside DCIM");
        Uri chosen=null;String base=null;
        for(UriPermission permission:context.getContentResolver().getPersistedUriPermissions()) {
            Uri uri=permission.getUri();
            if(!permission.isReadPermission() || !permission.isWritePermission()
                    || !"com.android.externalstorage.documents".equals(uri.getAuthority())
                    || !DocumentsContract.isTreeUri(uri))continue;
            String id=DocumentsContract.getTreeDocumentId(uri);
            if(!id.startsWith("primary:"))continue;
            String candidate=id.substring("primary:".length());
            while(candidate.endsWith("/"))candidate=candidate.substring(0,candidate.length()-1);
            if((candidate.isEmpty() || relative.equals(candidate) || relative.startsWith(candidate+"/"))
                    && (base==null || candidate.length()>base.length())) {chosen=uri;base=candidate;}
        }
        if(chosen==null)throw new IOException("Grant primary DCIM folder access in Settings before saving");
        DocumentFile folder=DocumentFile.fromTreeUri(context,chosen);
        if(folder==null || !folder.isDirectory())throw new IOException("Granted capture folder is unavailable");
        String tail=relative.substring(base.length());
        for(String part:tail.split("/")) {
            if(part.isEmpty())continue;
            DocumentFile child=folder.findFile(part);
            if(child==null)child=folder.createDirectory(part);
            if(child==null || !child.isDirectory())throw new IOException("Cannot open capture subfolder: "+part);
            folder=child;
        }
        return folder;
    }
    public static synchronized void publish(Context context,Path source,Path destination) throws IOException {
        publish(context,source,destination,new Metrics());
    }
    public static synchronized void publish(Context context,Path source,Path destination,Metrics metrics) throws IOException {
        DocumentFile folder=timedIO(metrics,"folder_lookup",()->parent(context,destination));
        HasselbladPublication80.publish(source,destination.getFileName().toString(),new HasselbladPublication80.Store() {
            public boolean exists(String name)throws IOException {
                return timedIO(metrics,"name_check",()->HasselbladCaptureFiles80.exists(context,folder,name,metrics));
            }
            public HasselbladPublication80.Document create(String mime,String name)throws IOException {
                DocumentFile file=timed(metrics,"create",()->folder.createFile(mime,name));
                if(file==null)throw new IOException("Document provider refused image creation");
                return new HasselbladPublication80.Document() {
                    public OutputStream open()throws IOException {
                        OutputStream stream=timedIO(metrics,"open",()->context.getContentResolver().openOutputStream(file.getUri(),"w"));
                        if(stream==null)return null;
                        return new OutputStream() {
                            public void write(int b)throws IOException {timedIO(metrics,"write",()->{stream.write(b);return null;});}
                            public void write(byte[] b,int offset,int count)throws IOException {
                                timedIO(metrics,"write",()->{stream.write(b,offset,count);return null;});
                            }
                            public void flush()throws IOException {stream.flush();}
                            public void close()throws IOException {timedIO(metrics,"close",()->{stream.close();return null;});}
                        };
                    }
                    public long length(){return timed(metrics,"length",file::length);}
                    public String name(){return timed(metrics,"final_name",file::getName);}
                    public boolean rename(String finalName){return timed(metrics,"rename",()->file.renameTo(finalName));}
                    public boolean delete(){return timed(metrics,"cleanup",file::delete);}
                };
            }
        });
    }
}
