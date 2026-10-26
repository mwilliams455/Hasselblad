// 33^3 display-input cube. Native JPEG colour + finishing evaluated on the CPU.
uniform bool uColour92Enabled;
uniform highp sampler2D uColour92;
highp vec3 hb92At(ivec3 p) {
    return texelFetch(uColour92,ivec2(p.b*33+p.r,p.g),0).rgb;
}
highp vec3 hb92Colour(highp vec3 rgb) {
    highp vec3 p=clamp(rgb,0.0,1.0)*32.0;
    ivec3 lo=ivec3(floor(p)),hi=min(lo+ivec3(1),ivec3(32));
    highp vec3 f=fract(p);
    // Explicit highp interpolation avoids the low fractional precision permitted
    // for hardware linear filtering, visible with steep private profile tables.
    highp vec3 b0=mix(mix(hb92At(lo),hb92At(ivec3(hi.r,lo.g,lo.b)),f.r),
                       mix(hb92At(ivec3(lo.r,hi.g,lo.b)),hb92At(ivec3(hi.r,hi.g,lo.b)),f.r),f.g);
    highp vec3 b1=mix(mix(hb92At(ivec3(lo.r,lo.g,hi.b)),hb92At(ivec3(hi.r,lo.g,hi.b)),f.r),
                       mix(hb92At(ivec3(lo.r,hi.g,hi.b)),hb92At(hi),f.r),f.g);
    return mix(b0,b1,f.b);
}
highp vec3 hb89Tone(highp vec3 rgb){return uColour92Enabled?hb92Colour(rgb):rgb;}
