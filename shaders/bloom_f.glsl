//GLSL
#version 140
uniform sampler2D final_light;
uniform sampler2D normal_tex;
uniform float power;
uniform float desat;
uniform float scale;

in vec2 uv;

vec3 desaturate(vec3 input_color, float amount)
    {
    vec3 gray = vec3(dot(input_color, vec3(0.3, 0.59, 0.11)));
    return mix(input_color, gray, amount);
    }


void main()
    {
    vec4 color=texture(final_light, uv);
    vec3 final_color=desaturate(color.rgb, desat)*pow(color.a*scale, power);
    gl_FragData[0] = vec4(final_color, 1.0);
    }

