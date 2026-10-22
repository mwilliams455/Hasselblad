package com.particlesdevs.photoncamera.hasselblad;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Stage32 strict, read-only DNG centre-tile decoder. Intentionally offline and
 * entirely independent of Camera2/photo save. Only classic uncompressed 16-bit
 * single-plane RGGB strip TIFF and GainMap-only OpcodeList2 are accepted.
 * Output: 32x32 camera-linear RGB samples, NOT Hasselblad/Photon demosaic.
 * No full-frame RAW allocation; input was copied to a temporary private file.
 */
public final class HasselbladDngTileReader {
    private HasselbladDngTileReader() {}
    public static final int TILE_SIZE = 32;
    public static final int MAX_FILE_BYTES = 256 * 1024 * 1024;
    private static final long MAX_PIXELS = 100_000_000L;
    private static final int MAX_META = 8 * 1024 * 1024;
    private static final int MAX_OPCODES = 64;
    private static final int[] CFA_RGGB = {0,1,1,2};
    private static final int WIDTH=256, HEIGHT=257, BITS=258, COMPRESSION=259,
        PHOTOMETRIC=262, STRIP_OFFSETS=273, SAMPLES=277, ROWS_PER_STRIP=278,
        STRIP_COUNTS=279, PLANAR_CONFIG=284, SUB_IFDS=330,
        CFA_DIMS=33421, CFA_PATTERN=33422, DNG_VERSION=50706,
        BLACK=50714, WHITE=50717, CC1=50723, CC2=50724,
        ANALOG=50727, NEUTRAL=50728, FM1=50964, FM2=50965,
        OPCODE1=51008, OPCODE2=51009, OPCODE3=51022;

    public static final class Unsupported extends IOException {
        public final String code;
        Unsupported(String reason) { super(reason); code=reason; }
    }
    private static void must(boolean ok, String reason) throws Unsupported {
        if (!ok) throw new Unsupported(reason);
    }
    public static final class ReadResult {
        public final int width,height,originalBits,stripCount;
        public final String gainState;
        public final int gainMapCount, gainAppliedSamples;
        public final double[] forwardMatrix1, forwardMatrix2, calibration1, calibration2,
                analogBalance, asShotNeutral, cameraLinearTile;
        ReadResult(int w,int h,int b,int strips,String gs,int maps,int applied,
                double[] fm1,double[] fm2,double[] cc1,double[] cc2,double[] analog,
                double[] neutral,double[] rgb) {
            width=w;height=h;originalBits=b;stripCount=strips;gainState=gs;
            gainMapCount=maps;gainAppliedSamples=applied;
            forwardMatrix1=fm1;forwardMatrix2=fm2;calibration1=cc1;calibration2=cc2;
            analogBalance=analog;asShotNeutral=neutral;cameraLinearTile=rgb;
        }
        public boolean hasPcsInput() { return forwardMatrix1!=null && asShotNeutral!=null; }
    }
    private static final class Tag {
        final int type;final long count;final long at;final long entryAt;
        Tag(int ty,long ct,long off,long en){type=ty;count=ct;at=off;entryAt=en;}
    }
    private static final class Page {
        final Map<Integer,Tag> tags=new HashMap<>();
        long next;
    }
    private static final class Gain {
        int top,left,bottom,right,rowPitch,colPitch,pointsV,pointsH;
        double spacingV,spacingH,originV,originH;
        float[] grid;
        boolean affects(int row,int col) {
            return row>=top && row<bottom && col>=left && col<right &&
                (row-top)%rowPitch==0 && (col-left)%colPitch==0;
        }
        double at(int row,int col,int width,int height) {
            double y=Math.max(0,Math.min(pointsV-1,
                    ((row+0.5)/height-originV)/spacingV));
            double x=Math.max(0,Math.min(pointsH-1,
                    ((col+0.5)/width-originH)/spacingH));
            int iy=(int)Math.floor(y), ix=(int)Math.floor(x);
            int jy=Math.min(pointsV-1,iy+1), jx=Math.min(pointsH-1,ix+1);
            double fy=y-iy,fx=x-ix;
            return (1-fy)*((1-fx)*grid[iy*pointsH+ix]+fx*grid[iy*pointsH+jx])+
                fy*((1-fx)*grid[jy*pointsH+ix]+fx*grid[jy*pointsH+jx]);
        }
    }
    private static final class Tiff {
        final RandomAccessFile file;
        final long size;
        final ByteOrder endian;
        Tiff(RandomAccessFile f)throws IOException {
            file=f;size=f.length();
            must(size>=16&&size<=MAX_FILE_BYTES,"file_size_unsupported");
            f.seek(0);int a=f.read(),b=f.read();
            must((a=='I'&&b=='I')||(a=='M'&&b=='M'),"tiff_byte_order_unsupported");
            endian=a=='I'?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN;
            must(u16(2)==42,"bigtiff_or_unknown_magic");
        }
        void range(long at,long n)throws Unsupported {
            must(at>=0&&n>=0&&at<=size&&n<=size-at,"tiff_offset_outside_file");
        }
        int u16(long at)throws IOException {
            range(at,2);file.seek(at);int a=file.readUnsignedByte(),b=file.readUnsignedByte();
            return endian==ByteOrder.LITTLE_ENDIAN ? a|(b<<8): (a<<8)|b;
        }
        long u32(long at)throws IOException {
            range(at,4);file.seek(at);
            long a=file.readUnsignedByte(),b=file.readUnsignedByte(),
                    c=file.readUnsignedByte(),d=file.readUnsignedByte();
            return endian==ByteOrder.LITTLE_ENDIAN ? a|(b<<8)|(c<<16)|(d<<24):
                (a<<24)|(b<<16)|(c<<8)|d;
        }
        byte[] at(long start,int length)throws IOException {
            must(length>=0&&length<=MAX_META,"metadata_allocation_limit");
            range(start,length);byte[] result=new byte[length];
            file.seek(start);file.readFully(result);return result;
        }
        Page page(long position)throws IOException {
            must(position>=8,"invalid_ifd_location");
            int entries=u16(position);
            must(entries>0&&entries<=512,"ifd_entry_count_unsupported");
            long end=position+2L+entries*12L;
            range(end,4);
            Page p=new Page();
            for(int i=0;i<entries;i++){
                long where=position+2L+i*12L;
                int tag=u16(where),type=u16(where+2);
                long count=u32(where+4),value=u32(where+8);
                must(sizeOfType(type)>0,"unsupported_tiff_tag_type");
                long n=count*sizeOfType(type);
                must(count>0&&n>=0&&n<=MAX_META,"tag_value_too_large");
                long at=n<=4?where+8:value;
                range(at,n);
                must(!p.tags.containsKey(tag),"duplicate_tiff_tag");
                p.tags.put(tag,new Tag(type,count,at,where));
            }
            p.next=u32(end);
            return p;
        }
        byte[] bytes(Tag t)throws IOException {
            must(t!=null,"required_tiff_tag_missing");
            int n=(int)(t.count*sizeOfType(t.type));
            return at(t.at,n);
        }
        long[] ints(Tag tag,int max)throws IOException {
            must(tag!=null&&tag.count>0&&tag.count<=max,"integer_tag_wrong_count");
            must(tag.type==1||tag.type==3||tag.type==4||tag.type==7,"integer_tag_wrong_type");
            ByteBuffer b=ByteBuffer.wrap(bytes(tag)).order(endian);
            long[] result=new long[(int)tag.count];
            for(int i=0;i<result.length;i++){
                if(tag.type==1||tag.type==7) result[i]=b.get()&255L;
                else if(tag.type==3) result[i]=b.getShort()&0xffffL;
                else result[i]=Integer.toUnsignedLong(b.getInt());
            }
            return result;
        }
        double[] numbers(Tag tag,int expected)throws IOException {
            must(tag!=null&&tag.count==expected,"profile_tag_wrong_count");
            int kind=tag.type;
            must(kind==3||kind==4||kind==5||kind==8||kind==9||kind==10||kind==11||kind==12,
                "profile_tag_wrong_type");
            ByteBuffer b=ByteBuffer.wrap(bytes(tag)).order(endian);
            double[] arr=new double[expected];
            for(int i=0;i<expected;i++){
                double v;
                if(kind==3)v=b.getShort()&0xffff;
                else if(kind==4)v=Integer.toUnsignedLong(b.getInt());
                else if(kind==8)v=b.getShort();
                else if(kind==9)v=b.getInt();
                else if(kind==5||kind==10){
                    double num=kind==5?Integer.toUnsignedLong(b.getInt()):b.getInt();
                    double den=kind==5?Integer.toUnsignedLong(b.getInt()):b.getInt();
                    must(den!=0,"profile_zero_denominator");v=num/den;
                } else if(kind==11)v=b.getFloat();
                else v=b.getDouble();
                must(Double.isFinite(v),"profile_nonfinite");arr[i]=v;
            }
            return arr;
        }
        private static int sizeOfType(int t){
            switch(t){case 1:case 2:case 6:case 7:return 1;
                case 3:case 8:return 2;
                case 4:case 9:case 11:return 4;
                case 5:case 10:case 12:return 8;
                default:return 0;}
        }
    }
    private static Tag inherited(Page child,Page root,int id){
        Tag direct=child.tags.get(id);
        return direct!=null?direct:root.tags.get(id);
    }
    private static double[] optional(Tiff tif,Page p,Page root,int tag,int count)throws IOException {
        Tag x=inherited(p,root,tag);return x==null?null:tif.numbers(x,count);
    }
    private static Page[] locate(Tiff tif)throws IOException {
        long ifd0=tif.u32(4);
        Page root=tif.page(ifd0);
        List<Page> pages=new ArrayList<>();pages.add(root);
        Set<Long> seen=new HashSet<>();seen.add(ifd0);
        Tag sub=root.tags.get(SUB_IFDS);
        if(sub!=null){
            long[] subOffsets=tif.ints(sub,16);
            for(long offset:subOffsets) if(offset!=0){
                must(seen.add(offset),"duplicate_sub_ifd");pages.add(tif.page(offset));
            }
        }
        long next=root.next;
        for(int i=0;i<8&&next!=0;i++){
            must(seen.add(next),"cyclic_ifd_link");
            Page p=tif.page(next);pages.add(p);next=p.next;
        }
        must(next==0,"too_many_ifds");
        return pages.toArray(new Page[0]);
    }
    private static Page choose(Tiff tif,Page[] pages)throws IOException {
        Page best=null;long area=0;
        for(Page p:pages) {
            if(p.tags.get(PHOTOMETRIC)==null||p.tags.get(WIDTH)==null||p.tags.get(HEIGHT)==null)
                continue;
            if(tif.ints(p.tags.get(PHOTOMETRIC),1)[0]!=32803)continue;
            long w=tif.ints(p.tags.get(WIDTH),1)[0],h=tif.ints(p.tags.get(HEIGHT),1)[0];
            if(w*h>area){best=p;area=w*h;}
        }
        must(best!=null,"no_bayer_raw_ifd");return best;
    }
    private static List<Gain> gainMaps(byte[] blob,int w,int h)throws IOException {
        must(blob.length>=4,"opcode2_bad_framing");
        ByteBuffer b=ByteBuffer.wrap(blob).order(ByteOrder.BIG_ENDIAN);
        long count=Integer.toUnsignedLong(b.getInt());
        must(count>0&&count<=MAX_OPCODES,"opcode2_bad_count");
        List<Gain> maps=new ArrayList<>();
        for(int op=0;op<count;op++){
            must(b.remaining()>=16,"opcode2_truncated_header");
            long id=Integer.toUnsignedLong(b.getInt());
            int maj=b.get()&255,min=b.get()&255,patch=b.get()&255,rev=b.get()&255;
            long flags=Integer.toUnsignedLong(b.getInt());
            long length=Integer.toUnsignedLong(b.getInt());
            must(flags<=3 && maj==1 && (min>=3&&min<=7) && (min!=7||patch<=1) &&
                 length>=76&&length<=MAX_META&&length<=b.remaining(),"opcode2_invalid_header");
            must(id==9,"unsupported_opcode2_id");
            int end=b.position()+(int)length;
            Gain g=new Gain();
            long top=Integer.toUnsignedLong(b.getInt()),left=Integer.toUnsignedLong(b.getInt()),
                bottom=Integer.toUnsignedLong(b.getInt()),right=Integer.toUnsignedLong(b.getInt());
            long plane=Integer.toUnsignedLong(b.getInt()),planes=Integer.toUnsignedLong(b.getInt()),
                rowPitch=Integer.toUnsignedLong(b.getInt()),colPitch=Integer.toUnsignedLong(b.getInt()),
                pointsV=Integer.toUnsignedLong(b.getInt()),pointsH=Integer.toUnsignedLong(b.getInt());
            g.spacingV=b.getDouble();g.spacingH=b.getDouble();
            g.originV=b.getDouble();g.originH=b.getDouble();
            long mapPlanes=Integer.toUnsignedLong(b.getInt());
            must(top<bottom&&bottom<=h&&left<right&&right<=w&&plane==0&&planes==1&&mapPlanes==1,
                "opcode2_unsupported_area_or_plane");
            must(rowPitch==2&&colPitch==2&&pointsV>0&&pointsH>0&&pointsV*pointsH<=32768,
                "opcode2_unsupported_pitch_or_grid");
            must(Double.isFinite(g.spacingV)&&Double.isFinite(g.spacingH)&&
                Double.isFinite(g.originV)&&Double.isFinite(g.originH)&&
                g.spacingV>0&&g.spacingH>0&&g.spacingV<=4&&g.spacingH<=4&&
                Math.abs(g.originV)<=4&&Math.abs(g.originH)<=4,
                "opcode2_bad_coordinates");
            must(length==76+4*pointsV*pointsH,"opcode2_bad_grid_bytes");
            g.top=(int)top;g.left=(int)left;g.bottom=(int)bottom;g.right=(int)right;
            g.rowPitch=(int)rowPitch;g.colPitch=(int)colPitch;
            g.pointsV=(int)pointsV;g.pointsH=(int)pointsH;
            g.grid=new float[g.pointsV*g.pointsH];
            for(int k=0;k<g.grid.length;k++){
                float v=b.getFloat();
                must(Float.isFinite(v)&&v>0&&v<=32,"opcode2_invalid_gain");g.grid[k]=v;
            }
            must(b.position()==end,"opcode2_payload_size_mismatch");
            maps.add(g);
        }
        must(b.position()==blob.length,"opcode2_trailing_bytes");
        return maps;
    }
    private static boolean site(int yy,int xx,int ch){
        int index=((yy&1)<<1)|(xx&1);
        return CFA_RGGB[index]==ch;
    }
    private static double sample(double[][] raw,int yy,int xx,int ch,int baseY,int baseX){
        if(site(yy,xx,ch))return raw[yy-baseY][xx-baseX];
        double weighted=0,support=0;
        for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++){
            int row=yy+dy,col=xx+dx;
            if(!site(row,col,ch))continue;
            int weight=(dy==0?2:1)*(dx==0?2:1);
            weighted+=weight*raw[row-baseY][col-baseX];support+=weight;
        }
        return weighted/support;
    }
    public static ReadResult read(File path)throws IOException {
        try(RandomAccessFile raf=new RandomAccessFile(path,"r")) {
            Tiff tif=new Tiff(raf);
            Page[] pages=locate(tif);Page root=pages[0],p=choose(tif,pages);
            int w=(int)tif.ints(p.tags.get(WIDTH),1)[0],h=(int)tif.ints(p.tags.get(HEIGHT),1)[0];
            must(w>=64&&h>=64&&w<=16384&&h<=16384&&(long)w*h<=MAX_PIXELS,
                "unsupported_raw_dimensions");
            must(tif.ints(p.tags.get(BITS),1)[0]==16,"raw_not_16bit");
            must(tif.ints(p.tags.get(COMPRESSION),1)[0]==1,"compressed_dng_not_supported");
            must(tif.ints(p.tags.get(SAMPLES),1)[0]==1,"multisample_dng_not_supported");
            Tag planar=p.tags.get(PLANAR_CONFIG);
            if(planar!=null)must(tif.ints(planar,1)[0]==1,"unsupported_planar_configuration");
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_DIMS),2),new long[]{2,2}),"non_RB_CFA_repeat");
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_PATTERN),4),new long[]{0,1,1,2}),"unsupported_CFA_not_RGGB");
            must(inherited(p,root,DNG_VERSION)!=null,"not_dng_missing_version");
            Tag t1=inherited(p,root,OPCODE1),t2=inherited(p,root,OPCODE2),t3=inherited(p,root,OPCODE3);
            must(t1==null&&t3==null,"unsupported_dng_opcode1_or_3");
            List<Gain> maps=t2==null?new ArrayList<>():gainMaps(tif.bytes(t2),w,h);
            String gainState=t2==null?"absent_not_shading_calibrated":"opcode2_gainmap_only";
            long[] off=tif.ints(p.tags.get(STRIP_OFFSETS),8192),
                    cnt=tif.ints(p.tags.get(STRIP_COUNTS),8192);
            must(off.length==cnt.length,"strip_offset_count_mismatch");
            long rp=tif.ints(p.tags.get(ROWS_PER_STRIP),1)[0];
            must(rp>=1&&rp<=Integer.MAX_VALUE,"invalid_rows_per_strip");
            long expected=(h+rp-1)/rp;
            must(expected==off.length,"strip_count_mismatch");
            long bytesPerRow=(long)w*2;
            for(int i=0;i<off.length;i++){
                long rows=Math.min(rp,h-i*rp);
                must(cnt[i]>=rows*bytesPerRow,"strip_not_contiguous_16bit_rows");
                tif.range(off[i],cnt[i]);
            }
            Tag bt=inherited(p,root,BLACK);
            must(bt!=null&&(bt.count==1||bt.count==4),"unsupported_black_level_shape");
            double[] black=tif.numbers(bt,(int)bt.count);
            must(black.length==1||black.length==4,"unsupported_black_level_repeat");
            Tag wt=inherited(p,root,WHITE);
            must(wt!=null&&(wt.count==1||wt.count==4),"unsupported_white_level_shape");
            double[] whites=tif.numbers(wt,(int)wt.count);
            double white=whites[0];
            for(double x:whites)must(x==white,"nonuniform_white_level_not_supported");
            must(white>0&&white<=65535,"white_level_invalid");
            for(double x:black)must(x>=0&&x<white,"black_level_invalid");
            double[] fm1=optional(tif,p,root,FM1,9),fm2=optional(tif,p,root,FM2,9),
                    cc1=optional(tif,p,root,CC1,9),cc2=optional(tif,p,root,CC2,9),
                    analog=optional(tif,p,root,ANALOG,3),neutral=optional(tif,p,root,NEUTRAL,3);
            int startX=((w-32)/2)&~1,startY=((h-32)/2)&~1;
            final int roi=34,baseX=startX-1,baseY=startY-1;
            must(baseX>=0&&baseY>=0&&baseX+roi<=w&&baseY+roi<=h,"tile_crop_invalid");
            double[][] mosaic=new double[roi][roi];
            int corrected=0;
            byte[] row=new byte[roi*2];
            for(int y=0;y<roi;y++){
                int gy=baseY+y;
                int strip=(int)(gy/rp);
                long pos=off[strip]+(gy%rp)*bytesPerRow+baseX*2L;
                tif.range(pos,row.length);raf.seek(pos);raf.readFully(row);
                ByteBuffer b=ByteBuffer.wrap(row).order(tif.endian);
                for(int x=0;x<roi;x++){
                    int gx=baseX+x;
                    int v=b.getShort()&0xffff;
                    double siteBlack=black.length==1?black[0]:black[((gy&1)<<1)|(gx&1)];
                    double norm=(v-siteBlack)/(white-siteBlack);
                    for(Gain g:maps) if(g.affects(gy,gx)){
                        norm=Math.min(norm*g.at(gy,gx,w,h),1.0);
                        corrected++;
                    }
                    must(Double.isFinite(norm),"gainmap_nonfinite_result");
                    mosaic[y][x]=norm;
                }
            }
            double[] camera=new double[32*32*3];
            int n=0;
            for(int y=1;y<=32;y++)for(int x=1;x<=32;x++){
                int yy=baseY+y,xx=baseX+x;
                for(int ch=0;ch<3;ch++){
                    double value=sample(mosaic,yy,xx,ch,baseY,baseX);
                    must(Double.isFinite(value),"demosaic_nonfinite_result");
                    camera[n++]=value;
                }
            }
            return new ReadResult(w,h,16,off.length,gainState,maps.size(),corrected,
                    fm1,fm2,cc1,cc2,analog,neutral,camera);
        }
    }
}
