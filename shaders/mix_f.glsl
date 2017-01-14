//GLSL
#version 140
in vec2 uv;

uniform sampler2D lut_tex;
uniform sampler2D lit_tex;
uniform sampler2D ao_tex;
uniform sampler2D ssr_tex;
uniform sampler2D forward_tex;
uniform sampler2D bloom_tex;
uniform sampler2D noise_tex;
uniform vec2 win_size;

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

void main()
    {
    vec4 color=texture(lit_tex,uv);
    vec4 color_forward=texture(forward_tex,uv);
    float ao=texture(ao_tex,uv).r;
    vec4 ssr=texture(ssr_tex,uv);
    vec4 bloom=texture(bloom_tex,uv);
    vec4 noise=texture(noise_tex,win_size*uv/64.0);

    vec3 final_color=mix(color.rgb,color_forward.rgb, color_forward.a);

    final_color+=ssr.rgb*color.a;

    final_color+=bloom.rgb;

    final_color.rgb*=ao;

    final_color.rgb=applyColorLUT(lut_tex, final_color.rgb);

    final_color+= ((noise.r + noise.g)-0.5)/255.0;

    gl_FragData[0]=vec4(final_color.rgb, 1.0);
    //gl_FragData[0]=vec4(ao, ao, ao, 1.0);
    }
