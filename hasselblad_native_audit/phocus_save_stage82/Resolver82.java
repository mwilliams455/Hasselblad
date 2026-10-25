package android.content;
import android.net.Uri;
import android.database.Cursor;
import android.os.Bundle;
import java.util.*;
import java.io.*;
import androidx.documentfile.provider.DocumentFile;

/** Synthetic query/stream provider used by the actual adapter tests. */
public class ContentResolver {
    public List<UriPermission> grants=new ArrayList<>();public List<Uri> opened=new ArrayList<>(),queried=new ArrayList<>();
    public int targetQueries,parentProbes,bulkQueries,openedCursors,closedCursors;
    public String mode="ok";public boolean opaqueFolder;
    public List<UriPermission> getPersistedUriPermissions(){return grants;}
    public OutputStream openOutputStream(Uri uri,String mode)throws IOException {
        if(!mode.equals("w"))throw new IOException("mode");opened.add(uri);
        DocumentFile f=DocumentFile.ALL.get(uri);if(f==null)throw new FileNotFoundException();f.bytes.reset();return f.bytes;
    }
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order) {
        if(selection!=null||args!=null||order!=null||!uri.tree)throw new AssertionError("Invalid query/grant");
        queried.add(uri);String kind;
        if(Arrays.equals(projection,new String[]{"document_id"})){kind="target";targetQueries++;}
        else if(Arrays.equals(projection,new String[]{"document_id","mime_type"})){kind="parent";parentProbes++;}
        else if(Arrays.equals(projection,new String[]{"_display_name"})){kind="bulk";bulkQueries++;}
        else throw new AssertionError("Unexpected projection");
        if(uri.children!=kind.equals("bulk"))throw new AssertionError("Wrong document/children URI");
        if(mode.equals(kind+"_permission")||mode.equals("second_target_permission")&&targetQueries==2&&kind.equals("target"))throw new SecurityException("Injected permission failure");
        if(kind.equals("target")&&(mode.equals("target_argument")||mode.equals("target_missing_other_id")))
            throw new IllegalArgumentException(mode.equals("target_argument")?"Unsupported lookup":"Failed to determine if unrelated is child of root: java.io.FileNotFoundException: Missing file for unrelated at /elsewhere");
        if(mode.equals("race")&&targetQueries==2&&kind.equals("target")) {
            int slash=uri.id.lastIndexOf('/');DocumentFile parent=DocumentFile.BYID.get(uri.id.substring(0,slash));
            parent.createFile("image/jpeg",uri.id.substring(slash+1)).bytes.write(42);
        }
        if(mode.equals(kind+"_cancel"))Thread.currentThread().interrupt();
        if(mode.equals(kind+"_null"))return null;
        DocumentFile f=DocumentFile.BYID.get(uri.id);List<String[]> rows=new ArrayList<>();
        if(kind.equals("target")) {
            if(f!=null)rows.add(new String[]{uri.id});
            else if(mode.equals("ok")||mode.equals("race")||mode.startsWith("parent_")||mode.equals("second_target_permission"))
                throw new IllegalArgumentException("Failed to determine if "+uri.id+" is child of "+uri.treeId+": java.io.FileNotFoundException: Missing file for "+uri.id+" at /synthetic-primary");
        } else if(kind.equals("parent")) {
            if(f==null)return null;
            rows.add(new String[]{uri.id,f.directory?"vnd.android.document/directory":f.mime});
        } else {
            if(f==null||!f.directory)throw new AssertionError("Wrong bulk folder");
            for(String name:f.children.keySet())rows.add(new String[]{name});
        }
        if(mode.equals(kind+"_empty"))rows.clear();
        if(mode.equals(kind+"_wrong_id")){rows.clear();rows.add(new String[]{"wrong","vnd.android.document/directory"});}
        if(mode.equals(kind+"_not_directory")){rows.clear();rows.add(new String[]{uri.id,"image/jpeg"});}
        if(mode.equals(kind+"_duplicate")){rows.clear();rows.add(new String[]{uri.id,"vnd.android.document/directory"});rows.add(rows.get(0));}
        if(mode.equals(kind+"_unnamed"))rows.add(new String[]{null});
        openedCursors++;
        return new Cursor(){int index=-1;boolean closed;
            public int getColumnIndexOrThrow(String name){
                if(mode.equals(kind+"_column"))throw new IllegalArgumentException("Missing column");
                for(int i=0;i<projection.length;i++)if(projection[i].equals(name))return i;
                throw new IllegalArgumentException("Unexpected column");
            }
            public boolean moveToNext(){if(mode.equals(kind+"_cursor"))throw new IllegalStateException("Cursor failed");return ++index<rows.size();}
            public String getString(int column){return rows.get(index)[column];}
            public Bundle getExtras(){Bundle b=new Bundle();b.loading=mode.equals(kind+"_loading");b.error=mode.equals(kind+"_error")?"Provider error":null;return b;}
            public void close(){if(closed)throw new AssertionError("Double close");closed=true;closedCursors++;}
        };
    }
}
