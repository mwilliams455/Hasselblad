// Display-domain relative tone only. No RAW colour LUT, white balance or exposure gain.
uniform bool uTone89Enabled;
uniform highp sampler2D uTone89;
highp vec3 hb89Decode(highp vec3 v) {
    return mix(v/12.92,pow((v+0.055)/1.055,vec3(2.4)),step(vec3(0.04045),v));
}
highp vec3 hb89Encode(highp vec3 v) {
    return mix(v*12.92,1.055*pow(v,vec3(1.0/2.4))-0.055,step(vec3(0.0031308),v));
}
highp float hb89Entry(highp float i) {
    highp vec2 pair=texture(uTone89,vec2((i+0.5)/1024.0,0.5)).rg;
    return dot(pair,vec2(65280.0,255.0))/65535.0;
}
highp vec3 hb89Tone(highp vec3 colour) {
    if(!uTone89Enabled)return colour;
    highp vec3 linear=hb89Decode(clamp(colour,0.0,1.0));
    highp float y=dot(linear,vec3(0.2126,0.7152,0.0722));
    highp float x=clamp(hb89Encode(vec3(y)).r,0.0,1.0)*1023.0;
    highp float lo=floor(x);
    highp float mapped=mix(hb89Entry(lo),hb89Entry(min(lo+1.0,1023.0)),x-lo);
    highp float target=hb89Decode(vec3(mapped)).r;
    if(y<0.0000001)return vec3(mapped);
    // A common gain preserves linear RGB ratios. Limit it before any channel clips.
    highp float peak=max(linear.r,max(linear.g,linear.b));
    highp float gain=min(target/y,1.0/max(peak,0.0000001));
    return hb89Encode(clamp(linear*gain,0.0,1.0));
}
