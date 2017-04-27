//GLSL
#version 140
uniform mat4 trans_apiclip_of_camera_to_apiview_of_camera;
uniform sampler2D depth_tex;
uniform sampler2D final_light;
uniform vec4 fog_color;
uniform vec4 fog_config;
uniform float dof_near;
uniform float dof_far;

in vec2 uv;

const float PI = 3.14159265358;

void main()
    {
    vec4 color=texture(final_light,uv);
    float depth=texture(depth_tex,uv).r * 2.0 - 1.0;
    vec4 view_pos = trans_apiclip_of_camera_to_apiview_of_camera * vec4( uv.xy * 2.0 - vec2(1.0), depth, 1.0);
    view_pos.xyz /= view_pos.w;

    float fog_start=fog_config.x;
    float fog_stop=fog_config.y;
    float fog_power=fog_config.z;
    float fog_mix=fog_config.w;

    float fog_factor=fog_mix*pow(min(1.0, max(0.0,-view_pos.z-fog_start)/(fog_stop-fog_start)),fog_power);
    vec4 final=mix(color,fog_color,fog_factor);

    float z=-view_pos.z +dof_near;

    float dof_factor_far=sin(min(1.0, z/dof_far)*PI);
    float dof_factor_near=pow(smoothstep(0.0, 0.9, dof_factor_far), 2.0);
    float dof_factor=mix(dof_factor_near, dof_factor_far, max(0.0, (z-(dof_far*0.5))/dof_far));

    final.a=dof_factor;
    //final=vec4(dof_factor);

    gl_FragData[0]=final;
    //gl_FragData[0]=vec4(dynamic_near);
    }
