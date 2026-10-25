"""Compile the actual Android save adapter with JVM document-provider spies.

This exercises grant selection/path confinement and the production adapter calls;
it is not an Android device/FUSE test.
"""
import subprocess
from pathlib import Path
def run(root,work,compiler,test_source=None):
 src=work/'adapter-src';classes=work/'adapter-classes';src.mkdir(exist_ok=True);classes.mkdir(exist_ok=True)
 sources={
 'android/net/Uri.java':'''package android.net;import java.util.Objects;public class Uri {
 public final String authority,id,treeId;public final boolean tree,children;
 public Uri(String a,String i,boolean t){this(a,i,t,i,false);}
 public Uri(String a,String i,boolean t,String root,boolean c){authority=a;id=i;tree=t;treeId=root;children=c;}
 public String getAuthority(){return authority;}public String toString(){return "content://"+authority+"/tree/"+treeId+"/document/"+id+(children?"/children":"");}
 public boolean equals(Object o){if(!(o instanceof Uri))return false;Uri u=(Uri)o;return authority.equals(u.authority)&&id.equals(u.id)&&treeId.equals(u.treeId)&&children==u.children;}
 public int hashCode(){return Objects.hash(authority,id,treeId,children);}
 }''',
 'android/content/UriPermission.java':'''package android.content;import android.net.Uri;public class UriPermission {Uri uri;boolean read,write;public UriPermission(Uri u,boolean r,boolean w){uri=u;read=r;write=w;}public Uri getUri(){return uri;}public boolean isReadPermission(){return read;}public boolean isWritePermission(){return write;}}''',
 'android/os/Bundle.java':'''package android.os;public class Bundle {public boolean loading;public String error;public boolean getBoolean(String key,boolean fallback){return loading;}public String getString(String key){return error;}}''',
 'android/database/Cursor.java':'''package android.database;public interface Cursor extends AutoCloseable {int getColumnIndexOrThrow(String name);boolean moveToNext();String getString(int column);android.os.Bundle getExtras();void close();}''',
 'android/content/ContentResolver.java':(Path(__file__).with_name('Resolver82.java')).read_text(),
 'android/content/Context.java':'''package android.content;import androidx.documentfile.provider.DocumentFile;public class Context {public Context(){DocumentFile.ALL.clear();DocumentFile.BYID.clear();DocumentFile.ROOTS.clear();}public final ContentResolver resolver=new ContentResolver();public ContentResolver getContentResolver(){return resolver;}}''',
 'android/os/Environment.java':'''package android.os;public class Environment {public static java.io.File getExternalStorageDirectory(){return new java.io.File("/hb80-primary");}}''',
 'android/provider/DocumentsContract.java':'''package android.provider;import android.net.Uri;public class DocumentsContract {
 public static final String EXTRA_LOADING="loading",EXTRA_ERROR="error";
 public static class Document {public static final String COLUMN_DISPLAY_NAME="_display_name",COLUMN_DOCUMENT_ID="document_id",COLUMN_MIME_TYPE="mime_type",MIME_TYPE_DIR="vnd.android.document/directory";}
 public static boolean isTreeUri(Uri u){return u.tree;}public static String getTreeDocumentId(Uri u){return u.treeId;}
 public static String getDocumentId(Uri u){return u.id;}
 public static Uri buildChildDocumentsUriUsingTree(Uri u,String id){if(!u.tree)throw new AssertionError("Tree grant lost");return new Uri(u.authority,id,true,u.treeId,true);}
 public static Uri buildDocumentUriUsingTree(Uri u,String id){if(!u.tree)throw new AssertionError("Tree grant lost");return new Uri(u.authority,id,true,u.treeId,false);}
 }''',
 'androidx/documentfile/provider/DocumentFile.java':(Path(__file__).with_name('DocumentFile82.java')).read_text()}
 for path,content in sources.items():
  p=src/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
 java=root/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 files=list(src.rglob('*.java'))+[java/'HasselbladPublication80.java',java/'HasselbladCaptureFiles80.java',Path(__file__).resolve().parents[1]/'phocus_save_stage80/Stage80AdapterCheck.java']
 if test_source is not None:files.append(test_source)
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,files)],check=True)
 output=subprocess.check_output(['java','-cp',str(classes),test_source.stem if test_source else 'Stage80AdapterCheck',str(work)],text=True);print(output,end='')
 return int(output.strip().split()[-1])
