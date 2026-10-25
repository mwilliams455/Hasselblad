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
        COLORIMETRIC_REFERENCE=50879, CAMERA_SIGNATURE=50931, PROFILE_SIGNATURE=50932,
        OPCODE1=51008, OPCODE2=51009, OPCODE3=51022;

    public static final class Unsupported extends IOException {
        public final String code;
        Unsupported(String reason) { super(reason); code=reason; }
    }
    private static void must(boolean ok, String reason) throws Unsupported {
        if (!ok) throw new Unsupported(reason);
    }
    public static final class IlluminantMetadata {
        public final double[] colorMatrix1,colorMatrix2;
        public final int light1,light2;
        public final String error;
        IlluminantMetadata(double[] a,double[] b,int l1,int l2,String e) {
            colorMatrix1=a;colorMatrix2=b;light1=l1;light2=l2;error=e;
        }
    }
    public static final class ReadResult {
        public final int width,height,originalBits,stripCount;
        public final String gainState;
        public final IlluminantMetadata illuminant;
        public final int gainMapCount, gainAppliedSamples;
        public final double[] forwardMatrix1, forwardMatrix2, calibration1, calibration2,
                analogBalance, asShotNeutral, cameraLinearTile;
        ReadResult(int w,int h,int b,int strips,String gs,int maps,int applied,
                double[] fm1,double[] fm2,double[] cc1,double[] cc2,double[] analog,
                double[] neutral,double[] rgb,IlluminantMetadata im) {
            width=w;height=h;originalBits=b;stripCount=strips;gainState=gs;
            gainMapCount=maps;gainAppliedSamples=applied;
            forwardMatrix1=fm1;forwardMatrix2=fm2;calibration1=cc1;calibration2=cc2;
            analogBalance=analog;asShotNeutral=neutral;cameraLinearTile=rgb;illuminant=im;
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
    /** Optional selector metadata must not break a previously supported manual preview. */
    private static IlluminantMetadata illuminant(Tiff tif,Page p,Page root) {
        try {
            for(int code:new int[]{52529,52530,52531})
                must(!p.tags.containsKey(code)&&!root.tags.containsKey(code),"three_illuminant_selection_unsupported");
            double[] a=optional(tif,p,root,50721,9),b=optional(tif,p,root,50722,9);
            must(a!=null,"colour_matrix_missing");
            int[] lights=new int[2];
            for(int i=0;i<2;i++) {
                Tag t=p.tags.get(50778+i);if(t==null)t=root.tags.get(50778+i);
                if(t!=null){must(t.count==1&&t.type==3,"calibration_illuminant_type_or_count");lights[i]=(int)tif.ints(t,1)[0];}
            }
            return new IlluminantMetadata(a,b,lights[0],lights[1],null);
        }catch(IOException e){return new IlluminantMetadata(null,null,0,0,e.getMessage());}
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
    private static byte[] signature(Tiff tif,Tag tag)throws IOException {
        if(tag==null)return new byte[0];
        must(tag.type==1||tag.type==2,"calibration_signature_wrong_type");
        byte[] value=tif.bytes(tag);
        int end=0;while(end<value.length&&value[end]!=0)end++;
        must(end<value.length,"calibration_signature_not_terminated");
        return Arrays.copyOf(value,end);
    }
    private static boolean calibrationMatches(Tiff tif,Page p,Page root)throws IOException {
        // DNG 1.7.1, pp.47-48 and p.100: missing signatures default to empty.
        return Arrays.equals(signature(tif,inherited(p,root,CAMERA_SIGNATURE)),
                             signature(tif,inherited(p,root,PROFILE_SIGNATURE)));
    }
    private static void requireSceneReference(Tiff tif,Page p,Page root)throws IOException {
        Tag tag=inherited(p,root,COLORIMETRIC_REFERENCE);
        if(tag!=null)must(tif.ints(tag,1)[0]==0,"output_referred_DNG_not_supported");
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
            requireSceneReference(tif,p,root);
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
            boolean useCalibration=calibrationMatches(tif,p,root);
            double[] fm1=optional(tif,p,root,FM1,9),fm2=optional(tif,p,root,FM2,9),
                    cc1=useCalibration?optional(tif,p,root,CC1,9):null,
                    cc2=useCalibration?optional(tif,p,root,CC2,9):null,
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
                    fm1,fm2,cc1,cc2,analog,neutral,camera,illuminant(tif,p,root));
        }
    }

    /** Stage43 whole-image grid preview. Samples are demosaiced at original RAW
     * coordinates before downsampling. Only three float Bayer rows are retained.
     * Existing Stage32 tile arithmetic is unchanged. No embedded preview is read.
     */
    public static final class PreviewResult {
        public final ReadResult metadata;
        public final int width,height,step,orientation;
        public final short[] cameraRgb16;
        public final long negativeChannels,overUnityChannels;
        public RawPreparation58 preparation58;
        PreviewResult(ReadResult m,int w,int h,int s,int o,short[] rgb,long neg,long over) {
            metadata=m;width=w;height=h;step=s;orientation=o;cameraRgb16=rgb;
            negativeChannels=neg;overUnityChannels=over;
        }
    }
    /** Optional Stage58 comparison and diagnostics. Counts cover unique decoded
     * Bayer rows, not every site in the RAW. Unclamped values are diagnostic:
     * they include noise and saturated samples, not recovered sensor detail. */
    public static final class RawPreparation58 {
        public final short[] rgb16;
        public final float[] unclampedRgb;
        public long decodedSites,rawBelowBlack,rawAtOrAboveWhite;
        public long rangeLowerClipped,rangeUpperClipped,gainClipEvents,gainClippedSites,gainClippedBelowWhite;
        public long unclampedNegativeChannels,unclampedOverUnityChannels,changedPreparedChannels;
        public final boolean unequalBlackLevels;
        RawPreparation58(int channels,boolean unequal) {
            rgb16=new short[channels];unclampedRgb=new float[channels];unequalBlackLevels=unequal;
        }
        public long[] counters() {
            return new long[]{decodedSites,rawBelowBlack,rawAtOrAboveWhite,rangeLowerClipped,rangeUpperClipped,
                gainClipEvents,gainClippedSites,gainClippedBelowWhite,unclampedNegativeChannels,
                unclampedOverUnityChannels,changedPreparedChannels};
        }
    }
    private static int reflected(int coordinate,int length) {
        return coordinate<0 ? -coordinate : coordinate>=length ? 2*length-2-coordinate : coordinate;
    }
    private static double gainReference(Gain g,int row,int col,int width,int height) {
        double y=Math.max(0,Math.min(g.pointsV-1,((row+.5)/height-g.originV)/g.spacingV));
        double x=Math.max(0,Math.min(g.pointsH-1,((col+.5)/width-g.originH)/g.spacingH));
        int y0=(int)y,x0=(int)x,y1=Math.min(y0+1,g.pointsV-1),x1=Math.min(x0+1,g.pointsH-1);
        double dy=y-y0,dx=x-x0;
        // Preserve Stage30's four-term float64 interpolation then float32 store.
        return g.grid[y0*g.pointsH+x0]*(1-dy)*(1-dx)+g.grid[y1*g.pointsH+x0]*dy*(1-dx)
            +g.grid[y0*g.pointsH+x1]*(1-dy)*dx+g.grid[y1*g.pointsH+x1]*dy*dx;
    }
    public static PreviewResult readPreview(File path,int maxPixels)throws IOException {
        return readPreviewInternal(path,maxPixels,false);
    }
    public static PreviewResult readPreviewWithPreparation58(File path,int maxPixels)throws IOException {
        return readPreviewInternal(path,maxPixels,true);
    }
    private static PreviewResult readPreviewInternal(File path,int maxPixels,boolean audit58)throws IOException {
        must(maxPixels>0&&maxPixels<=1048576,"preview_pixel_limit");
        try(RandomAccessFile raf=new RandomAccessFile(path,"r")) {
            Tiff tif=new Tiff(raf);Page[] pages=locate(tif);Page root=pages[0],p=choose(tif,pages);
            long wide=tif.ints(p.tags.get(WIDTH),1)[0],high=tif.ints(p.tags.get(HEIGHT),1)[0];
            must(wide>=64&&high>=64&&wide<=8192&&high<=8192&&wide*high<=16777216,
                "stage43_standard_raw_dimensions_required");
            int w=(int)wide,h=(int)high;
            must(tif.ints(p.tags.get(BITS),1)[0]==16,"raw_not_16bit");
            must(tif.ints(p.tags.get(COMPRESSION),1)[0]==1,"compressed_dng_not_supported");
            must(tif.ints(p.tags.get(SAMPLES),1)[0]==1,"multisample_dng_not_supported");
            must(inherited(p,root,DNG_VERSION)!=null,"not_dng_missing_version");
            requireSceneReference(tif,p,root);
            for(int tag:new int[]{PLANAR_CONFIG,266,339,50711}) {
                Tag t=inherited(p,root,tag);
                if(t!=null)must(tif.ints(t,1)[0]==1,"unsupported_raw_layout_"+tag);
            }
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_DIMS),2),new long[]{2,2}),"unsupported_CFA_repeat");
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_PATTERN),4),new long[]{0,1,1,2}),"unsupported_CFA_not_RGGB");
            for(int tag:new int[]{OPCODE1,OPCODE3,50712,50715,50716})
                must(inherited(p,root,tag)==null,"unsupported_raw_correction_"+tag);
            Tag active=inherited(p,root,50829);
            if(active!=null)must(Arrays.equals(tif.ints(active,4),new long[]{0,0,h,w}),"active_area_crop_not_supported");
            Tag origin=inherited(p,root,50719),crop=inherited(p,root,50720);
            if(origin!=null)must(Arrays.equals(tif.numbers(origin,2),new double[]{0,0}),"default_crop_origin_not_supported");
            if(crop!=null)must(Arrays.equals(tif.numbers(crop,2),new double[]{w,h}),"default_crop_size_not_supported");
            Tag orient=inherited(p,root,274);int orientation=orient==null?1:(int)tif.ints(orient,1)[0];
            must(orientation==1||orientation==3||orientation==6||orientation==8,"unsupported_orientation");
            Tag bt=inherited(p,root,BLACK),wt=inherited(p,root,WHITE);
            must(bt!=null&&(bt.count==1||bt.count==4),"unsupported_black_level_shape");
            double[] black=tif.numbers(bt,(int)bt.count);
            Tag repeat=inherited(p,root,50713);
            if(black.length==4)must(repeat!=null&&Arrays.equals(tif.ints(repeat,2),new long[]{2,2}),"unsupported_black_level_repeat");
            else if(repeat!=null)must(Arrays.equals(tif.ints(repeat,2),new long[]{1,1}),"unsupported_black_level_repeat");
            must(wt!=null&&(wt.count==1||wt.count==4),"unsupported_white_level_shape");
            double[] whites=tif.numbers(wt,(int)wt.count);double white=whites[0];
            must(white>0&&white<=65535,"white_level_invalid");
            for(double value:whites)must(value==white,"nonuniform_white_level_not_supported");
            for(double value:black)must(value>=0&&value<white,"black_level_invalid");
            boolean useCalibration=calibrationMatches(tif,p,root);
            double[] fm1=optional(tif,p,root,FM1,9),fm2=optional(tif,p,root,FM2,9),
                cc1=useCalibration?optional(tif,p,root,CC1,9):null,
                cc2=useCalibration?optional(tif,p,root,CC2,9):null,
                analog=optional(tif,p,root,ANALOG,3),neutral=optional(tif,p,root,NEUTRAL,3);
            must(fm1!=null&&neutral!=null,"DNG_forward_matrix_and_neutral_required");
            must((fm2==null||Arrays.equals(fm1,fm2))&&(cc2==null||(cc1!=null&&Arrays.equals(cc1,cc2))),
                "dual_illuminant_interpolation_not_supported");
            Tag opcode=inherited(p,root,OPCODE2);
            List<Gain> maps=opcode==null?new ArrayList<>():gainMaps(tif.bytes(opcode),w,h);
            long[] offsets=tif.ints(p.tags.get(STRIP_OFFSETS),8192),counts=tif.ints(p.tags.get(STRIP_COUNTS),8192);
            long rowsPerStrip=tif.ints(p.tags.get(ROWS_PER_STRIP),1)[0];
            must(rowsPerStrip>0&&rowsPerStrip<=Integer.MAX_VALUE&&offsets.length==counts.length&&
                (h+rowsPerStrip-1)/rowsPerStrip==offsets.length,"strip_count_mismatch");
            for(int i=0;i<offsets.length;i++) {
                long rows=Math.min(rowsPerStrip,h-i*rowsPerStrip);
                must(counts[i]>=rows*w*2L,"strip_not_contiguous_16bit_rows");tif.range(offsets[i],counts[i]);
            }
            int step=Math.max(1,(int)Math.ceil(Math.sqrt((double)w*h/maxPixels)));
            while((long)((w+step-1)/step)*((h+step-1)/step)>maxPixels)step++;
            int pw=(w+step-1)/step,ph=(h+step-1)/step;
            short[] rgb=new short[pw*ph*3];
            double maxBlack=black[0];boolean unequal=false;
            for(double level:black){maxBlack=Math.max(maxBlack,level);unequal|=level!=black[0];}
            double commonRange=white-maxBlack;
            RawPreparation58 prep=audit58?new RawPreparation58(rgb.length,unequal):null;
            float[][] corrected=audit58?new float[3][w]:null,unclamped=audit58?new float[3][w]:null;
            boolean[] counted=audit58?new boolean[h]:null;
            float[][] rowCache=new float[3][w];int[] cachedRow={-1,-1,-1};
            byte[] bytes=new byte[w*2];long negative=0,over=0;int applied=0;
            for(int py=0;py<ph;py++) {
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                int y=py*step;
                for(int dy=-1;dy<=1;dy++) {
                    int gy=reflected(y+dy,h),slot=gy%3;
                    if(cachedRow[slot]==gy)continue;
                    int strip=(int)(gy/rowsPerStrip);
                    long position=offsets[strip]+(gy%rowsPerStrip)*w*2L;
                    tif.range(position,bytes.length);raf.seek(position);raf.readFully(bytes);
                    ByteBuffer b=ByteBuffer.wrap(bytes).order(tif.endian);
                    boolean countRow=audit58&&!counted[gy];
                    for(int x=0;x<w;x++) {
                        int raw=b.getShort()&65535;
                        float siteBlack=(float)(black.length==1?black[0]:black[((gy&1)<<1)|(x&1)]);
                        float norm=(raw-siteBlack)/((float)white-siteBlack);
                        double exactBlack=black.length==1?black[0]:black[((gy&1)<<1)|(x&1)];
                        float signed=audit58?(float)((raw-exactBlack)/commonRange):0;
                        float bounded=Math.max(0f,Math.min(1f,signed)),unlimited=signed;
                        boolean gainClipped=false;long events=0;
                        for(Gain g:maps)if(g.affects(gy,x)) {
                            double gain=gainReference(g,gy,x,w,h);
                            norm=(float)Math.min(norm*gain,1.);applied++;
                            if(audit58) {
                                double product=bounded*gain;
                                if(product>1){gainClipped=true;events++;}
                                bounded=(float)Math.min(product,1.);
                                unlimited=(float)(unlimited*gain);
                            }
                        }
                        must(Float.isFinite(norm),"gainmap_nonfinite_result");rowCache[slot][x]=norm;
                        if(audit58) {
                            must(Float.isFinite(unlimited),"stage58_unclamped_diagnostic_overflow");
                            corrected[slot][x]=bounded;unclamped[slot][x]=unlimited;
                            if(countRow) {
                                prep.decodedSites++;
                                if(raw<exactBlack)prep.rawBelowBlack++;
                                if(raw>=white)prep.rawAtOrAboveWhite++;
                                if(signed<0)prep.rangeLowerClipped++;
                                if(signed>1)prep.rangeUpperClipped++;
                                prep.gainClipEvents+=events;
                                if(gainClipped){prep.gainClippedSites++;if(raw<white)prep.gainClippedBelowWhite++;}
                            }
                        }
                    }
                    cachedRow[slot]=gy;if(audit58)counted[gy]=true;
                }
                for(int px=0;px<pw;px++) {
                    int x=px*step;
                    for(int ch=0;ch<3;ch++) {
                        float value,correctedValue=0,unclampedValue=0;
                        if(site(y,x,ch)) {
                            value=rowCache[y%3][x];
                            if(audit58){correctedValue=corrected[y%3][x];unclampedValue=unclamped[y%3][x];}
                        } else {
                            float sum=0,support=0,correctedSum=0,unclampedSum=0;
                            for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
                                int gy=reflected(y+dy,h),gx=reflected(x+dx,w);
                                if(!site(gy,gx,ch))continue;
                                int weight=(dy==0?2:1)*(dx==0?2:1);
                                sum+=rowCache[gy%3][gx]*weight;support+=weight;
                                if(audit58){correctedSum+=corrected[gy%3][gx]*weight;unclampedSum+=unclamped[gy%3][gx]*weight;}
                            }
                            must(support>0,"demosaic_support_missing");value=sum/support;
                            if(audit58){correctedValue=correctedSum/support;unclampedValue=unclampedSum/support;}
                        }
                        if(value<0)negative++;if(value>1)over++;
                        int index=(py*pw+px)*3+ch;
                        rgb[index]=(short)(int)(Math.max(0f,Math.min(1f,value))*65535f);
                        if(audit58) {
                            must(Float.isFinite(unclampedValue),"stage58_unclamped_demosaic_overflow");
                            prep.rgb16[index]=(short)(int)(Math.max(0f,Math.min(1f,correctedValue))*65535f);
                            prep.unclampedRgb[index]=unclampedValue;
                            if(unclampedValue<0)prep.unclampedNegativeChannels++;
                            if(unclampedValue>1)prep.unclampedOverUnityChannels++;
                            if(rgb[index]!=prep.rgb16[index])prep.changedPreparedChannels++;
                        }
                    }
                }
            }
            ReadResult metadata=new ReadResult(w,h,16,offsets.length,
                opcode==null?"absent":"opcode2_gainmap_only",maps.size(),applied,
                fm1,fm2,cc1,cc2,analog,neutral,new double[0],illuminant(tif,p,root));
            PreviewResult result=new PreviewResult(metadata,pw,ph,step,orientation,rgb,negative,over);
            result.preparation58=prep;return result;
        }
    }

    /** Exact prepared mosaic for a bounded 64x64 output; never samples a frame edge.
     *  Quantizes BEFORE interpolation. Does not assert original Phocus DNG import parity. */
    public static final class Bounded75 {
        public final ReadResult metadata;
        public final short[] bayer;
        public final int x,y,orientation;
        public final long belowBlack,atWhite,gainClips;
        Bounded75(ReadResult m,short[] b,int x,int y,int o,long below,long white,long clips) {
            metadata=m;bayer=b;this.x=x;this.y=y;orientation=o;
            belowBlack=below;atWhite=white;gainClips=clips;
        }
    }
    public static Bounded75 readBounded75(File path,int region)throws IOException {
        must(region>=0&&region<5,"stage75_region_invalid");
        try(RandomAccessFile raf=new RandomAccessFile(path,"r")) {
            Tiff tif=new Tiff(raf);Page[] pages=locate(tif);Page root=pages[0],p=choose(tif,pages);
            long wide=tif.ints(p.tags.get(WIDTH),1)[0],high=tif.ints(p.tags.get(HEIGHT),1)[0];
            must(wide>=128&&high>=128&&wide<=8192&&high<=8192&&wide*high<=16777216,
                "stage75_standard_raw_dimensions_required");
            int w=(int)wide,h=(int)high;
            must(tif.ints(p.tags.get(BITS),1)[0]==16,"raw_not_16bit");
            must(tif.ints(p.tags.get(COMPRESSION),1)[0]==1,"compressed_dng_not_supported");
            must(tif.ints(p.tags.get(SAMPLES),1)[0]==1,"multisample_dng_not_supported");
            must(inherited(p,root,DNG_VERSION)!=null,"not_dng_missing_version");
            requireSceneReference(tif,p,root);
            for(int tag:new int[]{PLANAR_CONFIG,266,339,50711}) {
                Tag t=inherited(p,root,tag);
                if(t!=null)must(tif.ints(t,1)[0]==1,"unsupported_raw_layout_"+tag);
            }
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_DIMS),2),new long[]{2,2}),"unsupported_CFA_repeat");
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_PATTERN),4),new long[]{0,1,1,2}),"unsupported_CFA_not_RGGB");
            for(int tag:new int[]{OPCODE1,OPCODE3,50712,50715,50716})
                must(inherited(p,root,tag)==null,"unsupported_raw_correction_"+tag);
            Tag active=inherited(p,root,50829);
            if(active!=null)must(Arrays.equals(tif.ints(active,4),new long[]{0,0,h,w}),"active_area_crop_not_supported");
            Tag origin=inherited(p,root,50719),crop=inherited(p,root,50720);
            if(origin!=null)must(Arrays.equals(tif.numbers(origin,2),new double[]{0,0}),"default_crop_origin_not_supported");
            if(crop!=null)must(Arrays.equals(tif.numbers(crop,2),new double[]{w,h}),"default_crop_size_not_supported");
            Tag orient=inherited(p,root,274);int orientation=orient==null?1:(int)tif.ints(orient,1)[0];
            must(orientation==1||orientation==3||orientation==6||orientation==8,"unsupported_orientation");
            Tag bt=inherited(p,root,BLACK),wt=inherited(p,root,WHITE);
            must(bt!=null&&(bt.count==1||bt.count==4),"unsupported_black_level_shape");
            double[] black=tif.numbers(bt,(int)bt.count);
            Tag repeat=inherited(p,root,50713);
            if(black.length==4)must(repeat!=null&&Arrays.equals(tif.ints(repeat,2),new long[]{2,2}),"unsupported_black_level_repeat");
            else if(repeat!=null)must(Arrays.equals(tif.ints(repeat,2),new long[]{1,1}),"unsupported_black_level_repeat");
            must(wt!=null&&(wt.count==1||wt.count==4),"unsupported_white_level_shape");
            double[] whites=tif.numbers(wt,(int)wt.count);double white=whites[0];
            must(white>0&&white<=65535,"white_level_invalid");
            for(double value:whites)must(value==white,"nonuniform_white_level_not_supported");
            for(double value:black)must(value>=0&&value<white,"black_level_invalid");
            boolean useCalibration=calibrationMatches(tif,p,root);
            double[] fm1=optional(tif,p,root,FM1,9),fm2=optional(tif,p,root,FM2,9),
                cc1=useCalibration?optional(tif,p,root,CC1,9):null,
                cc2=useCalibration?optional(tif,p,root,CC2,9):null,
                analog=optional(tif,p,root,ANALOG,3),neutral=optional(tif,p,root,NEUTRAL,3);
            must(fm1!=null&&neutral!=null,"DNG_forward_matrix_and_neutral_required");
            must((fm2==null||Arrays.equals(fm1,fm2))&&(cc2==null||(cc1!=null&&Arrays.equals(cc1,cc2))),
                "dual_illuminant_interpolation_not_supported");
            Tag opcode=inherited(p,root,OPCODE2);
            List<Gain> maps=opcode==null?new ArrayList<>():gainMaps(tif.bytes(opcode),w,h);
            long[] offsets=tif.ints(p.tags.get(STRIP_OFFSETS),8192),counts=tif.ints(p.tags.get(STRIP_COUNTS),8192);
            long rowsPerStrip=tif.ints(p.tags.get(ROWS_PER_STRIP),1)[0];
            must(rowsPerStrip>0&&rowsPerStrip<=Integer.MAX_VALUE&&offsets.length==counts.length&&
                (h+rowsPerStrip-1)/rowsPerStrip==offsets.length,"strip_count_mismatch");
            for(int i=0;i<offsets.length;i++) {
                long rows=Math.min(rowsPerStrip,h-i*rowsPerStrip);
                must(counts[i]>=rows*w*2L,"strip_not_contiguous_16bit_rows");tif.range(offsets[i],counts[i]);
            }

            // Regions are output origins in sensor coordinates. All halos contain real samples.
            int x=((w-64)/2)&~1,y=((h-64)/2)&~1;
            if(region>0){x=(region==1||region==3)?32:((w-96)&~1);
                y=(region==1||region==2)?32:((h-96)&~1);}
            must(x>=32&&y>=32&&x+96<=w&&y+96<=h,"stage75_halo_outside_sensor");
            double maxBlack=black[0];for(double level:black)maxBlack=Math.max(maxBlack,level);
            double commonRange=white-maxBlack;
            short[] bayer=new short[128*128];byte[] bytes=new byte[256];
            long below=0,atWhite=0,clips=0;int applied=0;
            for(int row=0;row<128;row++) {
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG tile cancelled");
                int gy=y-32+row,strip=(int)(gy/rowsPerStrip);
                long position=offsets[strip]+(gy%rowsPerStrip)*w*2L+(x-32)*2L;
                tif.range(position,bytes.length);raf.seek(position);raf.readFully(bytes);
                ByteBuffer b=ByteBuffer.wrap(bytes).order(tif.endian);
                for(int col=0;col<128;col++) {
                    int gx=x-32+col,raw=b.getShort()&65535;
                    double siteBlack=black.length==1?black[0]:black[((gy&1)<<1)|(gx&1)];
                    if(raw<siteBlack)below++;if(raw>=white)atWhite++;
                    float bounded=Math.max(0f,Math.min(1f,(float)((raw-siteBlack)/commonRange)));
                    for(Gain g:maps)if(g.affects(gy,gx)) {
                        double product=bounded*gainReference(g,gy,gx,w,h);
                        if(product>1)clips++;
                        bounded=(float)Math.min(product,1.);applied++;
                    }
                    must(Float.isFinite(bounded)&&bounded>=0,"stage75_gainmap_invalid_result");
                    bayer[row*128+col]=(short)(int)(bounded*65535f);
                }
            }
            ReadResult metadata=new ReadResult(w,h,16,offsets.length,
                opcode==null?"absent":"opcode2_gainmap_only",maps.size(),applied,
                fm1,fm2,cc1,cc2,analog,neutral,new double[0],illuminant(tif,p,root));
            return new Bounded75(metadata,bayer,x,y,orientation,below,atWhite,clips);
        }
    }

    public static final class Prepared76 {
        public final ReadResult metadata;
        public final short[] bayer;
        public final int orientation;
        public final long belowBlack,atWhite,gainClips;
        Prepared76(ReadResult m,short[] b,int o,long below,long white,long clips) {
            metadata=m;bayer=b;orientation=o;belowBlack=below;atWhite=white;gainClips=clips;
        }
    }
    /** Same quantization/order as Stage75, read once for a full-scene interior render. */
    public static Prepared76 readPrepared76(File path)throws IOException {
        try(RandomAccessFile raf=new RandomAccessFile(path,"r")) {
            Tiff tif=new Tiff(raf);Page[] pages=locate(tif);Page root=pages[0],p=choose(tif,pages);
            long wide=tif.ints(p.tags.get(WIDTH),1)[0],high=tif.ints(p.tags.get(HEIGHT),1)[0];
            must(wide>=128&&high>=128&&wide<=8192&&high<=8192&&wide*high<=16777216,
                "stage76_standard_raw_dimensions_required");
            int w=(int)wide,h=(int)high;
            must(tif.ints(p.tags.get(BITS),1)[0]==16,"raw_not_16bit");
            must(tif.ints(p.tags.get(COMPRESSION),1)[0]==1,"compressed_dng_not_supported");
            must(tif.ints(p.tags.get(SAMPLES),1)[0]==1,"multisample_dng_not_supported");
            must(inherited(p,root,DNG_VERSION)!=null,"not_dng_missing_version");
            requireSceneReference(tif,p,root);
            for(int tag:new int[]{PLANAR_CONFIG,266,339,50711}) {
                Tag t=inherited(p,root,tag);
                if(t!=null)must(tif.ints(t,1)[0]==1,"unsupported_raw_layout_"+tag);
            }
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_DIMS),2),new long[]{2,2}),"unsupported_CFA_repeat");
            must(Arrays.equals(tif.ints(inherited(p,root,CFA_PATTERN),4),new long[]{0,1,1,2}),"unsupported_CFA_not_RGGB");
            for(int tag:new int[]{OPCODE1,OPCODE3,50712,50715,50716})
                must(inherited(p,root,tag)==null,"unsupported_raw_correction_"+tag);
            Tag active=inherited(p,root,50829);
            if(active!=null)must(Arrays.equals(tif.ints(active,4),new long[]{0,0,h,w}),"active_area_crop_not_supported");
            Tag origin=inherited(p,root,50719),crop=inherited(p,root,50720);
            if(origin!=null)must(Arrays.equals(tif.numbers(origin,2),new double[]{0,0}),"default_crop_origin_not_supported");
            if(crop!=null)must(Arrays.equals(tif.numbers(crop,2),new double[]{w,h}),"default_crop_size_not_supported");
            Tag orient=inherited(p,root,274);int orientation=orient==null?1:(int)tif.ints(orient,1)[0];
            must(orientation==1||orientation==3||orientation==6||orientation==8,"unsupported_orientation");
            Tag bt=inherited(p,root,BLACK),wt=inherited(p,root,WHITE);
            must(bt!=null&&(bt.count==1||bt.count==4),"unsupported_black_level_shape");
            double[] black=tif.numbers(bt,(int)bt.count);
            Tag repeat=inherited(p,root,50713);
            if(black.length==4)must(repeat!=null&&Arrays.equals(tif.ints(repeat,2),new long[]{2,2}),"unsupported_black_level_repeat");
            else if(repeat!=null)must(Arrays.equals(tif.ints(repeat,2),new long[]{1,1}),"unsupported_black_level_repeat");
            must(wt!=null&&(wt.count==1||wt.count==4),"unsupported_white_level_shape");
            double[] whites=tif.numbers(wt,(int)wt.count);double white=whites[0];
            must(white>0&&white<=65535,"white_level_invalid");
            for(double value:whites)must(value==white,"nonuniform_white_level_not_supported");
            for(double value:black)must(value>=0&&value<white,"black_level_invalid");
            boolean useCalibration=calibrationMatches(tif,p,root);
            double[] fm1=optional(tif,p,root,FM1,9),fm2=optional(tif,p,root,FM2,9),
                cc1=useCalibration?optional(tif,p,root,CC1,9):null,
                cc2=useCalibration?optional(tif,p,root,CC2,9):null,
                analog=optional(tif,p,root,ANALOG,3),neutral=optional(tif,p,root,NEUTRAL,3);
            must(fm1!=null&&neutral!=null,"DNG_forward_matrix_and_neutral_required");
            must((fm2==null||Arrays.equals(fm1,fm2))&&(cc2==null||(cc1!=null&&Arrays.equals(cc1,cc2))),
                "dual_illuminant_interpolation_not_supported");
            Tag opcode=inherited(p,root,OPCODE2);
            List<Gain> maps=opcode==null?new ArrayList<>():gainMaps(tif.bytes(opcode),w,h);
            long[] offsets=tif.ints(p.tags.get(STRIP_OFFSETS),8192),counts=tif.ints(p.tags.get(STRIP_COUNTS),8192);
            long rowsPerStrip=tif.ints(p.tags.get(ROWS_PER_STRIP),1)[0];
            must(rowsPerStrip>0&&rowsPerStrip<=Integer.MAX_VALUE&&offsets.length==counts.length&&
                (h+rowsPerStrip-1)/rowsPerStrip==offsets.length,"strip_count_mismatch");
            for(int i=0;i<offsets.length;i++) {
                long rows=Math.min(rowsPerStrip,h-i*rowsPerStrip);
                must(counts[i]>=rows*w*2L,"strip_not_contiguous_16bit_rows");tif.range(offsets[i],counts[i]);
            }


            double maxBlack=black[0];for(double level:black)maxBlack=Math.max(maxBlack,level);
            double commonRange=white-maxBlack;
            short[] bayer=new short[w*h];byte[] bytes=new byte[w*2];
            long below=0,atWhite=0,clips=0;int applied=0;
            for(int gy=0;gy<h;gy++) {
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preparation cancelled");
                int strip=(int)(gy/rowsPerStrip);
                long position=offsets[strip]+(gy%rowsPerStrip)*w*2L;
                tif.range(position,bytes.length);raf.seek(position);raf.readFully(bytes);
                ByteBuffer b=ByteBuffer.wrap(bytes).order(tif.endian);
                for(int gx=0;gx<w;gx++) {
                    int raw=b.getShort()&65535;
                    double siteBlack=black.length==1?black[0]:black[((gy&1)<<1)|(gx&1)];
                    if(raw<siteBlack)below++;if(raw>=white)atWhite++;
                    float bounded=Math.max(0f,Math.min(1f,(float)((raw-siteBlack)/commonRange)));
                    for(Gain g:maps)if(g.affects(gy,gx)) {
                        double product=bounded*gainReference(g,gy,gx,w,h);
                        if(product>1)clips++;
                        bounded=(float)Math.min(product,1.);applied++;
                    }
                    must(Float.isFinite(bounded)&&bounded>=0,"stage76_gainmap_invalid_result");
                    bayer[gy*w+gx]=(short)(int)(bounded*65535f);
                }
            }
            ReadResult metadata=new ReadResult(w,h,16,offsets.length,
                opcode==null?"absent":"opcode2_gainmap_only",maps.size(),applied,
                fm1,fm2,cc1,cc2,analog,neutral,new double[0],illuminant(tif,p,root));
            return new Prepared76(metadata,bayer,orientation,below,atWhite,clips);
        }
    }
}
