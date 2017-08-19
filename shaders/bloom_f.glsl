//GLSL
#version 140
uniform sampler2D final_light;
uniform sampler2D normal_tex;
uniform float glow_power;

in vec2 uv;

void main()
    {
    vec4 color=texture(final_light, uv);
    float glow=texture(normal_tex, uv).b;
    float gloss= color.a;

    vec3 final_color=color.xyz*glow+pow(color.xyz*glow, vec3(4.0));
    final_color*=glow_power;

    final_color+=clamp((color.xyz-0.2)*2.0, 0.0, 1.0)*gloss;

    gl_FragData[0] = vec4(final_color, 1.0);
    }

