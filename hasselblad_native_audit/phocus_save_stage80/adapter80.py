"""Compile the actual Android save adapter with JVM document-provider spies.

This exercises grant selection/path confinement and the production adapter calls;
it is not an Android device/FUSE test.
"""
import subprocess
from pathlib import Path
def run(root,work,compiler,test_source=None):
 src=work/'adapter-src';classes=work/'adapter-classes';src.mkdir(exist_ok=True);classes.mkdir(exist_ok=True)
 sources={
 'android/net/Uri.java':'''package android.net;public class Uri {public final String authority,id;public final boolean tree;public Uri(String a,String i,boolean t){authority=a;id=i;tree=t;}public String getAuthority(){return authority;}public String toString(){return "content://"+authority+"/"+id;}}''',
 'android/content/UriPermission.java':'''package android.content;import android.net.Uri;public class UriPermission {Uri uri;boolean read,write;public UriPermission(Uri u,boolean r,boolean w){uri=u;read=r;write=w;}public Uri getUri(){return uri;}public boolean isReadPermission(){return read;}public boolean isWritePermission(){return write;}}''',
 'android/os/Bundle.java':'''package android.os;public class Bundle {public boolean loading;public boolean getBoolean(String key,boolean fallback){return loading;}}''',
 'android/database/Cursor.java':'''package android.database;public interface Cursor extends AutoCloseable {int getColumnIndexOrThrow(String name);boolean moveToNext();String getString(int column);android.os.Bundle getExtras();void close();}''',
 'android/content/ContentResolver.java':'''package android.content;
 import android.net.Uri;import android.database.Cursor;import android.os.Bundle;import java.util.*;import java.io.*;import androidx.documentfile.provider.DocumentFile;
 public class ContentResolver {
 public List<UriPermission> grants=new ArrayList<>();public List<Uri> opened=new ArrayList<>();
 public int queries,closedCursors,queryFailureAt,queryVisits,creates;public String queryMode="ok";public boolean loading;
 public List<UriPermission> getPersistedUriPermissions(){return grants;}
 public OutputStream openOutputStream(Uri uri,String mode)throws IOException {if(!mode.equals("w"))throw new IOException("mode");opened.add(uri);DocumentFile f=DocumentFile.ALL.get(uri);if(f==null)throw new FileNotFoundException();f.bytes.reset();return f.bytes;}
 public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order) {
 queries++;if(projection.length!=1||!projection[0].equals("_display_name")||selection!=null||args!=null||order!=null)throw new AssertionError("Unexpected filename query");
 if(queryFailureAt==queries)throw new SecurityException("Injected query failure");
 if(queryMode.equals("null"))return null;
 DocumentFile folder=DocumentFile.ALL.get(uri);if(folder==null||!folder.directory)throw new AssertionError("Query URI is not current folder");
 if(queryMode.equals("race")&&queries==2)folder.createFile("image/jpeg","target.jpg").bytes.write(42);
 List<String> names=new ArrayList<>(folder.children.keySet());if(queryMode.equals("unnamed"))names.add(null);
 return new Cursor(){int index=-1;boolean closed;
 public int getColumnIndexOrThrow(String name){if(!name.equals("_display_name"))throw new AssertionError();if(queryMode.equals("column"))throw new IllegalArgumentException("Missing column");return 0;}
 public boolean moveToNext(){if(queryMode.equals("cursor"))throw new IllegalStateException("Broken cursor");if(queryMode.equals("cancel"))Thread.currentThread().interrupt();if(++index<names.size()){queryVisits++;return true;}return false;}
 public String getString(int column){return names.get(index);}
 public Bundle getExtras(){Bundle b=new Bundle();b.loading=loading;return b;}
 public void close(){if(closed)throw new AssertionError("Cursor closed twice");closed=true;closedCursors++;}
 };}
 }''',
 'android/content/Context.java':'''package android.content;public class Context {public final ContentResolver resolver=new ContentResolver();public ContentResolver getContentResolver(){return resolver;}}''',
 'android/os/Environment.java':'''package android.os;public class Environment {public static java.io.File getExternalStorageDirectory(){return new java.io.File("/hb80-primary");}}''',
 'android/provider/DocumentsContract.java':'''package android.provider;import android.net.Uri;public class DocumentsContract {
 public static final String EXTRA_LOADING="loading";public static class Document {public static final String COLUMN_DISPLAY_NAME="_display_name";}
 public static boolean isTreeUri(Uri u){return u.tree;}public static String getTreeDocumentId(Uri u){return u.id;}
 public static String getDocumentId(Uri u){return u.id;}
 public static Uri buildChildDocumentsUriUsingTree(Uri u,String id){if(!u.id.equals(id))throw new AssertionError("Wrong document ID");return u;}
 }''',
 'androidx/documentfile/provider/DocumentFile.java':'''package androidx.documentfile.provider;
 import android.content.Context;import android.net.Uri;import java.util.*;import java.io.*;
 public class DocumentFile {
 public static Map<Uri,DocumentFile> ALL=new HashMap<>(),ROOTS=new HashMap<>();public static Uri selected;public static int nameReads;
 public Map<String,DocumentFile> children=new LinkedHashMap<>();public ByteArrayOutputStream bytes=new ByteArrayOutputStream();
 public String name,mime;public boolean directory;public Uri uri;public DocumentFile parent;
 public DocumentFile(String n,boolean d){name=n;directory=d;uri=new Uri("com.android.externalstorage.documents",UUID.randomUUID().toString(),false);ALL.put(uri,this);}
 public static DocumentFile fromTreeUri(Context c,Uri u){selected=u;return ROOTS.get(u);}
 public boolean isDirectory(){return directory;}public DocumentFile findFile(String n){return children.get(n);}
 public DocumentFile createDirectory(String n){DocumentFile f=new DocumentFile(n,true);f.parent=this;children.put(n,f);return f;}
 public DocumentFile createFile(String mime,String n){if(n.endsWith(".tmp"))throw new SecurityException("Public .tmp denied");DocumentFile f=new DocumentFile(n,false);f.mime=mime;f.parent=this;children.put(n,f);return f;}
 public Uri getUri(){return uri;}public long length(){return bytes.size();}public String getName(){nameReads++;return name;}
 public boolean renameTo(String n){if(parent.children.containsKey(n))return false;parent.children.remove(name);name=n;parent.children.put(n,this);ALL.remove(uri);uri=new Uri("com.android.externalstorage.documents",UUID.randomUUID().toString(),false);ALL.put(uri,this);return true;}
 public boolean delete(){ALL.remove(uri);parent.children.remove(name);return true;}
 }
 '''}
 for path,content in sources.items():
  p=src/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 java=root/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 files=list(src.rglob('*.java'))+[java/'HasselbladPublication80.java',java/'HasselbladCaptureFiles80.java',Path(__file__).with_name('Stage80AdapterCheck.java')]
 if test_source is not None:files.append(test_source)
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,files)],check=True)
 output=subprocess.check_output(['java','-cp',str(classes),test_source.stem if test_source else 'Stage80AdapterCheck',str(work)],text=True);print(output,end='')
 return int(output.strip().split()[-1])
