package androidx.documentfile.provider;
import android.content.Context;
import android.net.Uri;
import java.util.*;
import java.io.*;

/** JVM provider fixture, not shipped in the APK. */
public class DocumentFile {
    public static Map<Uri,DocumentFile> ALL=new HashMap<>(),ROOTS=new HashMap<>();
    public static Map<String,DocumentFile> BYID=new HashMap<>();
    public static Uri selected;public static int nameReads;
    public Map<String,DocumentFile> children=new LinkedHashMap<>();
    public ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    public String name,mime;public boolean directory;public Uri uri;public DocumentFile parent;
    public DocumentFile(String name,boolean directory) {
        this.name=name;this.directory=directory;
        bind("unbound:"+UUID.randomUUID(),"unbound");
    }
    public void bind(String id,String tree) {
        if(uri!=null){ALL.remove(uri);BYID.remove(uri.id,this);}
        uri=new Uri("com.android.externalstorage.documents",id,true,tree,false);
        ALL.put(uri,this);BYID.put(id,this);
        for(DocumentFile f:children.values())f.bind(childId(f.name),tree);
    }
    private String childId(String name){return uri.id+(uri.id.endsWith(":")?"":"/")+name;}
    public static DocumentFile fromTreeUri(Context c,Uri uri) {
        selected=uri;DocumentFile root=ROOTS.get(uri);
        if(root!=null)root.bind(c.resolver.opaqueFolder?"opaque:folder":uri.id,uri.treeId);
        return root;
    }
    public boolean isDirectory(){return directory;}
    public DocumentFile findFile(String name){return children.get(name);}
    public DocumentFile createDirectory(String name){DocumentFile f=new DocumentFile(name,true);f.parent=this;children.put(name,f);f.bind(childId(name),uri.treeId);return f;}
    public DocumentFile createFile(String mime,String name){
        if(name.endsWith(".tmp"))throw new SecurityException("Public .tmp denied");
        DocumentFile f=new DocumentFile(name,false);f.mime=mime;f.parent=this;children.put(name,f);f.bind(childId(name),uri.treeId);return f;
    }
    public Uri getUri(){return uri;}
    public long length(){return bytes.size();}
    public String getName(){nameReads++;return name;}
    public boolean renameTo(String name) {
        if(parent.children.containsKey(name))return false;
        parent.children.remove(this.name);this.name=name;parent.children.put(name,this);
        bind(parent.childId(name),uri.treeId);return true;
    }
    public boolean delete(){ALL.remove(uri);BYID.remove(uri.id,this);parent.children.remove(name);return true;}
}
