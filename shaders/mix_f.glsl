//GLSL
#version 140
in vec2 uv;
uniform sampler2D forward_tex;
uniform sampler2D final_color;
#ifndef DISABLE_LUT
uniform sampler2D lut_tex;
#endif
#ifndef DISABLE_AO
uniform sampler2D ao;
#endif
#ifndef DISABLE_SSR
uniform sampler2D ssr;
#endif
#ifndef DISABLE_BLOOM
uniform sampler2D bloom_blur;
#endif
#ifndef DISABLE_DITHERING
uniform sampler2D noise_tex;
#endif
//uniform vec2 win_size;

vec3 applyColorLUT(sampler2D lut, vec3 color)
    {
    float lutSize = float(textureSize(lut, 0).y);
    color = clamp(color, vec3(0.5 / lutSize), vec3(1.0 - 0.5 / lutSize));
    vec2 texcXY = vec2(color.r * 1.0 / lutSize, 1.0 - color.g);

    int frameZ = int(color.b * lutSize);
    float offsZ = fract(color.b * lutSize);

    vec3 sample1 = textureLod(lut, texcXY + vec2((frameZ) / lutSize, 0), 0).rgb;
    vec3 sample2 = textureLod(lut, texcXY + vec2( (frameZ + 1) / lutSize, 0), 0).rgb;

    return mix(sample1, sample2, offsZ);
    }

vec3 srgbEncode(vec3 color){
   float r = color.r < 0.0031308 ? 12.92 * color.r : 1.055 * pow(color.r, 1.0/2.4) - 0.055;
   float g = color.g < 0.0031308 ? 12.92 * color.g : 1.055 * pow(color.g, 1.0/2.4) - 0.055;
   float b = color.b < 0.0031308 ? 12.92 * color.b : 1.055 * pow(color.b, 1.0/2.4) - 0.055;
   return vec3(r, g, b);
}

void main()
    {
    vec4 color=texture(final_color,uv);
    vec4 color_forward=texture(forward_tex,uv);
    vec2 win_size=textureSize(final_color, 0).xy;
    vec3 final_color=color.rgb;

    #ifndef DISABLE_SSR
    vec4 ssr_tex=texture(ssr,uv);
    final_color+=ssr_tex.rgb*color.a;
    #endif

    #ifndef DISABLE_BLOOM
    vec4 bloom=texture(bloom_blur,uv);
    final_color+=bloom.rgb;
    #endif

    #ifndef DISABLE_AO
    float ao_tex=texture(ao,uv).r;
    final_color.rgb*=ao_tex;
    #endif


    final_color=mix(final_color.rgb, color_forward.rgb, color_forward.a);


    #ifndef DISABLE_LUT
    final_color.rgb=applyColorLUT(lut_tex, srgbEncode(final_color.rgb));
    //final_color.rgb=lookup(lut_tex, final_color.rgb);
    //final_color=vec3(sRGB(final_color.r),sRGB(final_color.g),sRGB(final_color.b));
    #endif

    #ifndef DISABLE_DITHERING
    vec4 noise=texture(noise_tex,win_size*uv/64.0);
    final_color+= ((noise.r + noise.g)-0.5)/255.0;
    #endif

    //final_color=vec3(ao_tex,ao_tex,ao_tex);
    //final_color+= ((noise.r + noise.g)-0.5)/255.0;

    gl_FragData[0]=vec4(final_color.rgb, color.a);
    }
