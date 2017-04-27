//GLSL
#version 140
uniform mat4 trans_apiclip_of_camera_to_apiview_of_camera;
uniform sampler2D normal_tex;
uniform sampler2D depth_tex;
uniform sampler2D random_tex;
uniform float sample_rad;
uniform float intensity;
uniform float scale;
uniform float bias;
uniform float fade_distance;

in vec2 uv;

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

vec3 getPosition(vec2 uv)
    {
    float depth=texture(depth_tex,uv).r * 2.0 - 1.0;
    vec4 view_pos = trans_apiclip_of_camera_to_apiview_of_camera * vec4( uv.xy * 2.0 - vec2(1.0), depth, 1.0);
    view_pos.xyz /= view_pos.w;
    return view_pos.xyz;
    }

float doAmbientOcclusion(vec2 tcoord,vec2 uv, vec3 p, vec3 norm)
    {
    vec3 diff = getPosition(tcoord + uv) - p;
    vec3 v = normalize(diff);
    float d = length(diff)*scale;
    return max(0.0,dot(norm,v)-bias)*(1.0/(1.0+d))*intensity;
    }

void main()
    {
    const vec2 vec[4] = vec2[4](vec2(1,0), vec2(-1,0), vec2(0,1),vec2(0,-1));
    float ao=0.0;
    vec3 p =getPosition(uv);
    vec3 n =unpack_normal_octahedron(texture(normal_tex,uv).xy);
    vec2 win_size=textureSize(normal_tex, 0).xy;
    vec2 rand = normalize(texture(random_tex, win_size * uv / textureSize(random_tex, 0).xy).xy * 2.0 - 1.0);
    float rad = sample_rad;

    //int iterations = 8;
    for (int j = 0; j < 8; ++j)
    {
      vec2 coord1 = reflect(vec[j],rand)*rad;
      vec2 coord2 = vec2(coord1.x*0.707 - coord1.y*0.707,
                  coord1.x*0.707 + coord1.y*0.707);

      ao += doAmbientOcclusion(uv,coord1*0.25, p, n);
      ao += doAmbientOcclusion(uv,coord2*0.5, p, n);
      ao += doAmbientOcclusion(uv,coord1*0.75, p, n);
      ao += doAmbientOcclusion(uv,coord2, p, n);
    }
    //ao/=float(iterations)*4.0;
    ao*=0.0625;
    ao=(1.0-ao);
    //float co=0.1+pow((p.z/-fade_distance), 5.0);
    //ao=clamp(ao, co, 1.0);
    //vec3 color=texture(lit_tex,uv).rgb*ao;
    //vec3 color=vec3(1.0, 1.0, 1.0)*ao;
    gl_FragData[0]=vec4(ao,ao,ao, 1.0);
    }

