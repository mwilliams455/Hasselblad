package com.particlesdevs.photoncamera.hasselblad;

/** Immutable saved-JPEG controls. Radius and dark limit retain the recovered defaults. */
public final class HasselbladSharpen91 {
    public static final int MAX_AMOUNT=200, MAX_NOISE=32;
    public static final HasselbladSharpen91 OFF=new HasselbladSharpen91(false,100,0);
    public static final HasselbladSharpen91 DEFAULT=new HasselbladSharpen91(true,100,0);
    public final boolean enabled;
    public final int amount,noise;
    public HasselbladSharpen91(boolean enabled,int amount,int noise) {
        if(amount<0||amount>MAX_AMOUNT||noise<0||noise>MAX_NOISE)
            throw new IllegalArgumentException("Sharpening controls outside supported range");
        this.enabled=enabled;this.amount=amount;this.noise=noise;
    }
    public boolean active(){return enabled&&amount>0;}
    public String description(){return active()?"strength "+amount+", threshold "+noise+", radius 1, dark limit 10":"off";}
    String encode(){return "1:"+(enabled?1:0)+":"+amount+":"+noise;}
    static HasselbladSharpen91 decode(String value) {
        String[] fields=value.split(":",-1);
        if(fields.length!=4||!fields[0].equals("1")||!(fields[1].equals("0")||fields[1].equals("1")))
            throw new IllegalArgumentException("Invalid sharpening settings");
        return new HasselbladSharpen91(fields[1].equals("1"),Integer.parseInt(fields[2]),Integer.parseInt(fields[3]));
    }
}
