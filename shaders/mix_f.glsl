//GLSL
#version 140
in vec2 uv;
uniform sampler2D forward_tex;
uniform sampler2D final_color;
uniform sampler2D normal_tex;
uniform vec4 brightness_contrast;
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
uniform sampler2D bloom;
#endif
#ifndef DISABLE_DITHERING
uniform sampler2D noise_tex;
#endif

uniform sampler2D forward_aux_tex;
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
    vec2 final_uv=uv+ (texture(forward_aux_tex, uv).rg);
    vec4 color=texture(final_color,final_uv);
    vec4 color_forward=texture(forward_tex,uv);
    vec2 win_size=textureSize(final_color, 0).xy;
    vec3 final_color=color.rgb;


    #ifndef DISABLE_SSR
    vec4 ssr_tex=texture(ssr,final_uv);
    final_color+=ssr_tex.rgb;
    //final_color+=mix(final_color*ssr_tex.rgb*gloss, ssr_tex.rgb*gloss, metallic);
    //final_color+=ssr_tex.rgb*gloss;//final_color+(ssr_tex.rgb*gloss);//mix(final_color*ssr_tex.rgb*gloss, final_color+ssr_tex.rgb*gloss, metallic);
    #endif



    final_color=mix(final_color.rgb, color_forward.rgb, color_forward.a);




    #ifndef DISABLE_LUT
    final_color.rgb=applyColorLUT(lut_tex, final_color.rgb);
    //final_color.rgb=applyColorLUT(lut_tex, srgbEncode(final_color.rgb));
    //final_color.rgb=lookup(lut_tex, final_color.rgb);
    //final_color=vec3(sRGB(final_color.r),sRGB(final_color.g),sRGB(final_color.b));
    #endif

    #ifndef DISABLE_BLOOM
    vec4 bloom_tex=texture(bloom,final_uv);
    final_color+=bloom_tex.rgb*0.5;
    #endif

    #ifndef DISABLE_SRGB
    final_color.r=pow(final_color.r, 1.0/2.2);
    final_color.g=pow(final_color.g, 1.0/2.2);
    final_color.b=pow(final_color.b, 1.0/2.2);
    #endif



    #ifndef DISABLE_DITHERING
    vec4 noise=texture(noise_tex,win_size*uv/64.0);
    final_color+= ((noise.r + noise.g)-0.5)/255.0;
    #endif

    #ifndef DISABLE_AO
    float ao_tex=texture(ao,final_uv).r;
    final_color.rgb*=ao_tex;
    #endif


    gl_FragData[0]=vec4(final_color.rgb, color.a);
    }
