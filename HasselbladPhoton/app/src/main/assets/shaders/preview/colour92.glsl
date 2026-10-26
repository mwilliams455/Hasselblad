// 33^3 display-input cube. Native JPEG colour + finishing evaluated on the CPU.
uniform bool uColour92Enabled;
uniform highp sampler2D uColour92;
highp vec3 hb92Colour(highp vec3 rgb) {
    highp vec3 p=clamp(rgb,0.0,1.0)*32.0;
    highp float lo=floor(p.b),hi=min(lo+1.0,32.0);
    highp vec2 a=vec2((lo*33.0+p.r+0.5)/1089.0,(p.g+0.5)/33.0);
    highp vec2 b=vec2((hi*33.0+p.r+0.5)/1089.0,(p.g+0.5)/33.0);
    return mix(texture(uColour92,a).rgb,texture(uColour92,b).rgb,p.b-lo);
}

highp vec3 hb89Tone(highp vec3 rgb){return uColour92Enabled?hb92Colour(rgb):rgb;}
