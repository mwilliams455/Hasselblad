#!/usr/bin/env python3
"""Focused profile selection and store failures using synthetic Android file adapters."""
import argparse,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
CONTEXT='''package android.content;
import java.io.File;
public final class Context {private final File files;public Context(File f){files=f;f.mkdirs();}public File getFilesDir(){return files;}}
'''
ATOMIC='''package android.util;
import java.io.*;import java.nio.file.*;
public final class AtomicFile {
 public static boolean failWrite,failFinish,silentFinishFailure;
 private final File base,pending;
 public AtomicFile(File f){base=f;pending=new File(f.getPath()+".new");}
 public FileInputStream openRead()throws IOException{return new FileInputStream(base);}
 public FileOutputStream startWrite()throws IOException{return new FileOutputStream(pending){
  @Override public void write(byte[] b)throws IOException{if(failWrite)throw new IOException("injected disk write failure");super.write(b);}
 };}
 public void finishWrite(FileOutputStream out){try{out.close();if(silentFinishFailure)return;if(failFinish)throw new IOException("injected rename failure");
  Files.move(pending.toPath(),base.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
 }catch(IOException e){throw new IllegalStateException(e);}}
 public void failWrite(FileOutputStream out){try{out.close();}catch(IOException ignored){}pending.delete();}
}
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--private-profiles',nargs=3,type=Path,metavar=('CURVE0','CURVE1','PACK'));a=p.parse_args()
    work=a.work.resolve();work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
    shutil.rmtree(work/'private-store',ignore_errors=True)
    stubs=work/'stubs';stubs.mkdir(exist_ok=True)
    (stubs/'Context.java').write_text(CONTEXT);(stubs/'AtomicFile.java').write_text(ATOMIC)
    java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
    compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
    sources=[java/(s+'.java') for s in ('HasselbladPreview90Changes','HasselbladLook84','HasselbladLookStore84','HasselbladTone83','HasselbladProfile43','HasselbladRenderer42')]
    subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,sources),str(stubs/'Context.java'),str(stubs/'AtomicFile.java'),
                            str(HERE.parent/'phocus_tone_stage83/Stage83Check.java'),str(HERE/'Stage84Check.java')],check=True)
    args=['java','-cp',str(classes),'Stage84Check',str(work)]
    if a.private_profiles:args.extend(str(p.resolve()) for p in a.private_profiles)
    subprocess.run(args,check=True)
if __name__=='__main__':main()
