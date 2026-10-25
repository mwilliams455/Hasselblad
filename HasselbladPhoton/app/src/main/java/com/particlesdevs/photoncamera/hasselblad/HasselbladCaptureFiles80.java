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
        private long rows,targetQueries,parentProbes,bulkQueries,missingTargetExceptions,queryFallbacks;
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
            result.put("name_lookup_target_queries",targetQueries);
            result.put("name_lookup_parent_probes",parentProbes);
            result.put("name_lookup_bulk_queries",bulkQueries);
            result.put("name_lookup_missing_target_exceptions",missingTargetExceptions);
            result.put("name_lookup_query_fallbacks",queryFallbacks);
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
    private static void complete(Cursor cursor)throws IOException {
        if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
        if(cursor.getExtras().getBoolean(DocumentsContract.EXTRA_LOADING,false)
                || cursor.getExtras().getString(DocumentsContract.EXTRA_ERROR)!=null)
            throw new IOException("Capture filename query is incomplete or failed");
    }
    private static boolean exists(Context context,Folder parent,String name,Metrics m)throws IOException {
        DocumentFile folder=parent.document;
        String parentId=DocumentsContract.getDocumentId(folder.getUri());
        // This path format belongs only to Android's primary external-storage provider.
        // Verify the actual granted folder ID against the canonical destination before
        // constructing a child ID. Unknown mappings retain the Stage81 bulk lookup.
        if(!parent.expectedId.equals(parentId))return bulkExists(context,folder,name,m);
        if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
        String targetId=parentId+"/"+name;
        Uri target=DocumentsContract.buildDocumentUriUsingTree(folder.getUri(),targetId);
        m.targetQueries++;
        Cursor targetResult;
        try {
            targetResult=context.getContentResolver().query(target,
                    new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID},null,null,null);
        }catch(IllegalArgumentException error) {
            // AOSP checks tree ancestry before querying metadata. A missing child is
            // wrapped in this precise message, without preserving the checked cause.
            // Unknown errors retain the complete bulk check; never guess absence.
            String missing="Failed to determine if "+targetId+" is child of "
                    +DocumentsContract.getTreeDocumentId(folder.getUri())
                    +": java.io.FileNotFoundException: Missing file for "+targetId+" at ";
            if(error.getMessage()==null || !error.getMessage().startsWith(missing)) {
                m.queryFallbacks++;return bulkExists(context,folder,name,m);
            }
            m.missingTargetExceptions++;targetResult=null;
        }
        try(Cursor cursor=targetResult) {
            if(cursor!=null) {
                complete(cursor);
                int column=cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
                if(cursor.moveToNext()) {
                    m.rows++;
                    if(!targetId.equals(cursor.getString(column)) || cursor.moveToNext())
                        throw new IOException("Capture document lookup returned an unexpected result");
                    complete(cursor);return true;
                }
                complete(cursor);
            }
        }
        // DocumentsProvider returns null for a missing document. Require a healthy,
        // accessible parent so an unavailable volume/grant is not treated as absence.
        if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
        m.parentProbes++;
        try(Cursor cursor=context.getContentResolver().query(folder.getUri(),new String[]{
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)) {
            if(cursor==null)throw new IOException("Cannot verify capture folder after a missing document lookup");
            complete(cursor);
            int id=cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int mime=cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE);
            if(!cursor.moveToNext() || !parentId.equals(cursor.getString(id))
                    || !DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(mime))
                    || cursor.moveToNext())throw new IOException("Capture folder probe returned an unexpected result");
            complete(cursor);return false;
        }
    }
    private static boolean bulkExists(Context context,DocumentFile folder,String name,Metrics m)throws IOException {
        m.bulkQueries++;
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(folder.getUri(),
                DocumentsContract.getDocumentId(folder.getUri()));
        try(Cursor cursor=context.getContentResolver().query(children,
                new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null)) {
            if(cursor==null)throw new IOException("Capture filename query returned no result");
            complete(cursor);
            int column=cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            while(cursor.moveToNext()) {
                if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
                m.rows++;
                String found=cursor.getString(column);
                if(found==null)throw new IOException("Capture filename query returned an unnamed document");
                if(name.equals(found))return true;
            }
            complete(cursor);
            return false;
        }
    }
    private static final class Folder {
        final DocumentFile document;final String expectedId;
        Folder(DocumentFile document,String expectedId){this.document=document;this.expectedId=expectedId;}
    }
    private static Folder parent(Context context,Path destination) throws IOException {
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
        return new Folder(folder,"primary:"+relative);
    }
    public static synchronized void publish(Context context,Path source,Path destination) throws IOException {
        publish(context,source,destination,new Metrics());
    }
    public static synchronized void publish(Context context,Path source,Path destination,Metrics metrics) throws IOException {
        Folder parent=timedIO(metrics,"folder_lookup",()->parent(context,destination));
        DocumentFile folder=parent.document;
        HasselbladPublication80.publish(source,destination.getFileName().toString(),new HasselbladPublication80.Store() {
            public boolean exists(String name)throws IOException {
                return timedIO(metrics,"name_check",()->HasselbladCaptureFiles80.exists(context,parent,name,metrics));
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
