"""Compile the actual Android save adapter with JVM document-provider spies.

This exercises grant selection/path confinement and the production adapter calls;
it is not an Android device/FUSE test.
"""
import subprocess
from pathlib import Path
def run(root,work,compiler):
 src=work/'adapter-src';classes=work/'adapter-classes';src.mkdir(exist_ok=True);classes.mkdir(exist_ok=True)
 sources={
 'android/net/Uri.java':'''package android.net;public class Uri {public final String authority,id;public final boolean tree;public Uri(String a,String i,boolean t){authority=a;id=i;tree=t;}public String getAuthority(){return authority;}public String toString(){return "content://"+authority+"/"+id;}}''',
 'android/content/UriPermission.java':'''package android.content;import android.net.Uri;public class UriPermission {Uri uri;boolean read,write;public UriPermission(Uri u,boolean r,boolean w){uri=u;read=r;write=w;}public Uri getUri(){return uri;}public boolean isReadPermission(){return read;}public boolean isWritePermission(){return write;}}''',
 'android/content/ContentResolver.java':'''package android.content;import android.net.Uri;import java.util.*;import java.io.*;import androidx.documentfile.provider.DocumentFile;public class ContentResolver {public List<UriPermission> grants=new ArrayList<>();public List<Uri> opened=new ArrayList<>();public List<UriPermission> getPersistedUriPermissions(){return grants;}public OutputStream openOutputStream(Uri uri,String mode)throws IOException {if(!mode.equals("w"))throw new IOException("mode");opened.add(uri);DocumentFile f=DocumentFile.ALL.get(uri);if(f==null)throw new FileNotFoundException();f.bytes.reset();return f.bytes;}}''',
 'android/content/Context.java':'''package android.content;public class Context {public final ContentResolver resolver=new ContentResolver();public ContentResolver getContentResolver(){return resolver;}}''',
 'android/os/Environment.java':'''package android.os;public class Environment {public static java.io.File getExternalStorageDirectory(){return new java.io.File("/hb80-primary");}}''',
 'android/provider/DocumentsContract.java':'''package android.provider;import android.net.Uri;public class DocumentsContract {public static boolean isTreeUri(Uri u){return u.tree;}public static String getTreeDocumentId(Uri u){return u.id;}}''',
 'androidx/documentfile/provider/DocumentFile.java':'''package androidx.documentfile.provider;
 import android.content.Context;import android.net.Uri;import java.util.*;import java.io.*;
 public class DocumentFile {
 public static Map<Uri,DocumentFile> ALL=new HashMap<>(),ROOTS=new HashMap<>();public static Uri selected;
 public Map<String,DocumentFile> children=new HashMap<>();public ByteArrayOutputStream bytes=new ByteArrayOutputStream();
 public String name,mime;public boolean directory;public Uri uri;public DocumentFile parent;
 public DocumentFile(String n,boolean d){name=n;directory=d;uri=new Uri("com.android.externalstorage.documents",UUID.randomUUID().toString(),false);ALL.put(uri,this);}
 public static DocumentFile fromTreeUri(Context c,Uri u){selected=u;return ROOTS.get(u);}
 public boolean isDirectory(){return directory;}public DocumentFile findFile(String n){return children.get(n);}
 public DocumentFile createDirectory(String n){DocumentFile f=new DocumentFile(n,true);f.parent=this;children.put(n,f);return f;}
 public DocumentFile createFile(String mime,String n){if(n.endsWith(".tmp"))throw new SecurityException("Public .tmp denied");DocumentFile f=new DocumentFile(n,false);f.mime=mime;f.parent=this;children.put(n,f);return f;}
 public Uri getUri(){return uri;}public long length(){return bytes.size();}public String getName(){return name;}
 public boolean renameTo(String n){if(parent.children.containsKey(n))return false;parent.children.remove(name);name=n;parent.children.put(n,this);ALL.remove(uri);uri=new Uri("com.android.externalstorage.documents",UUID.randomUUID().toString(),false);ALL.put(uri,this);return true;}
 public boolean delete(){ALL.remove(uri);parent.children.remove(name);return true;}
 }
 '''}
 for path,content in sources.items():
  p=src/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 java=root/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 files=list(src.rglob('*.java'))+[java/'HasselbladPublication80.java',java/'HasselbladCaptureFiles80.java',Path(__file__).with_name('Stage80AdapterCheck.java')]
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,files)],check=True)
 output=subprocess.check_output(['java','-cp',str(classes),'Stage80AdapterCheck',str(work)],text=True);print(output,end='')
 return int(output.strip().split()[-1])
