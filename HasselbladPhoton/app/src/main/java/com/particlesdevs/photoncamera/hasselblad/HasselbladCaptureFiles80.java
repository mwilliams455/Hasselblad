package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.content.UriPermission;
import android.net.Uri;
import android.os.Environment;
import android.provider.DocumentsContract;
import androidx.documentfile.provider.DocumentFile;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Path;

/** Uses the already granted primary-DCIM tree; never creates a public .tmp via FUSE. */
public final class HasselbladCaptureFiles80 {
    private HasselbladCaptureFiles80() {}
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
        DocumentFile folder=parent(context,destination);
        HasselbladPublication80.publish(source,destination.getFileName().toString(),new HasselbladPublication80.Store() {
            public boolean exists(String name){return folder.findFile(name)!=null;}
            public HasselbladPublication80.Document create(String mime,String name)throws IOException {
                DocumentFile file=folder.createFile(mime,name);
                if(file==null)throw new IOException("Document provider refused image creation");
                return new HasselbladPublication80.Document() {
                    public OutputStream open()throws IOException{return context.getContentResolver().openOutputStream(file.getUri(),"w");}
                    public long length(){return file.length();}
                    public String name(){return file.getName();}
                    public boolean rename(String finalName){return file.renameTo(finalName);}
                    public boolean delete(){return file.delete();}
                };
            }
        });
    }
}
