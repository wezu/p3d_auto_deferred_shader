//GLSL
#version 140
struct p3d_LightSourceParameters
    {
    vec4 color;
    vec4 position;
    vec3 spotDirection;
    float spotExponent;
    float spotCutoff;
    float spotCosCutoff;
    sampler2DShadow shadowMap;
    mat4 shadowMatrix;
    };
uniform p3d_LightSourceParameters spot;
uniform mat4 p3d_ProjectionMatrixInverse;
uniform mat4 p3d_ViewProjectionMatrixInverse;
uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4  trans_render_to_clip_of_spot;
uniform sampler2D albedo_tex;
uniform sampler2D normal_tex;
uniform sampler2D depth_tex;

//uniform mat4 trans_render_to_shadowcaster;

//uniform vec2 win_size;
uniform float light_radius;
uniform float light_fov;
uniform vec4 light_pos;
//uniform float near;
//uniform float bias;

in vec3 N;
in vec3 V;
//in vec4 shadow_uv;

// For each component of v, returns -1 if the component is < 0, else 1
vec2 sign_not_zero(vec2 v)
    {
    // Version with branches (for GLSL < 4.00)
    return vec2(v.x >= 0 ? 1.0 : -1.0, v.y >= 0 ? 1.0 : -1.0);
    }

// Packs a 3-component normal to 2 channels using octahedron normals
vec2 pack_normal_octahedron(vec3 v)
    {
    // Faster version using newer GLSL capatibilities
    v.xy /= dot(abs(v), vec3(1.0));
    // Branch-Less version
    return mix(v.xy, (1.0 - abs(v.yx)) * sign_not_zero(v.xy), step(v.z, 0.0));
    }


// Unpacking from octahedron normals, input is the output from pack_normal_octahedron
vec3 unpack_normal_octahedron(vec2 packed_nrm)
    {
    // Version using newer GLSL capatibilities
    vec3 v = vec3(packed_nrm.xy, 1.0 - abs(packed_nrm.x) - abs(packed_nrm.y));
    // Branch-Less version
    v.xy = mix(v.xy, (1.0 - abs(v.yx)) * sign_not_zero(v.xy), step(v.z, 0));
    return normalize(v);
    }

void main()
    {
    vec3 color=vec3(0.0, 0.0, 0.0);
    vec2 win_size=textureSize(depth_tex, 0).xy;
    vec2 uv=gl_FragCoord.xy/win_size;

    vec4 color_tex=texture(albedo_tex, uv);
    vec3 albedo=color_tex.rgb;
    vec4 normal_glow_gloss=texture(normal_tex,uv);
    vec3 normal=unpack_normal_octahedron(normal_glow_gloss.xy);
    float gloss=normal_glow_gloss.a;
    float glow=normal_glow_gloss.b;
    float depth=texture(depth_tex,uv).r * 2.0 - 1.0;

    //vec4 light_view_pos=spot.position;

    vec4 view_pos = p3d_ProjectionMatrixInverse * vec4( uv.xy * 2.0 - vec2(1.0), depth, 1.0);
    view_pos.xyz /= view_pos.w;

    //vec3 light_vec = -normalize(spot.spotDirection);
    vec3 light_vec = normalize(spot.position.xyz-view_pos.xyz);

    //diffuse
    float attenuation=1.0-(pow(distance(view_pos.xyz, spot.position.xyz)/light_radius*1.1, 2.0));
    float spotEffect = dot(normalize(spot.spotDirection), -light_vec);
    float falloff=0.0;
    if (spotEffect > spot.spotCosCutoff)
      falloff = pow(spotEffect, 25.0);
    attenuation*=falloff;

    color+=spot.color.rgb*max(dot(normal.xyz,light_vec), 0.0)*attenuation;
    //spec
    vec3 view_vec = normalize(-view_pos.xyz);
    vec3 reflect_vec=normalize(reflect(light_vec,normal.xyz));
    float spec=pow(max(dot(reflect_vec, -view_vec), 0.0), 100.0*gloss)*gloss*attenuation;

    vec4 final=vec4((color*albedo)+spot.color.rgb*spec, spec+gloss);

    //shadows
    //the fragment world pos reconstructed from depth:
    vec4 world_pos = p3d_ViewProjectionMatrixInverse * vec4( uv.xy * 2.0 - vec2(1.0), depth, 1.0);
    world_pos.xyz /= world_pos.w;
    world_pos.xyz-=light_pos.xyz;//move the pos to the position of the light source???
    vec4 shadow_uv=trans_render_to_clip_of_spot*world_pos;//transform the post to the clip space of the light
    //do voodoo???
    shadow_uv.xy*=0.5; //idk?
    shadow_uv.xy+=2.0; //huh?
    //...missing step???
    //shadow lookup
    float shadow= textureProj(spot.shadowMap, shadow_uv, 0.01);

    final*=shadow;

    gl_FragData[0]=final;
    }
