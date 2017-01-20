//GLSL
#version 140
// This parameters should be configured according to Far and Near plane
// of your main camera
const float zFar = 500.0;
const float zNear = 1.0;
const float maxDelta = 0.005;   // Delta depth test value
const float rayLength =0.001;   // 0..1 Ray length (percent of zFar)
const int stepsCount = 8;      // Quality. With too match value may
                                // be problem on non-nvidia cards

const float fade = 1.0;         // Fade out reflection

in vec2 uv;

uniform sampler2D normal_tex;
uniform sampler2D depth_tex;
uniform sampler2D final_light;
uniform mat4 trans_apiclip_of_camera_to_apiview_of_camera;
uniform mat4 trans_apiview_of_camera_to_apiclip_of_camera;

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

float linearizeDepth(float depth)
    {
    return (2.0 * zNear) / (zFar + zNear - depth * (zFar - zNear));
    }


vec4 raytrace(vec3 startPos,
              vec3 endPos,
              mat4 mat_proj,
              sampler2D albedo,
              sampler2D depth)
    {
    // Convert start and end positions of reflect vector from the
    // camera space to the screen space
    vec4 startPosSS = mat_proj * vec4(startPos,1.0);
    startPosSS /= startPosSS.w;
    startPosSS.xy = startPosSS.xy;
    vec4 endPosSS =mat_proj * vec4(endPos,1.0);
    endPosSS /= endPosSS.w;
    endPosSS.xy = endPosSS.xy;
    // Reflection vector in the screen space
    //vec3 vectorSS = normalize(endPosSS.xyz - startPosSS.xyz)*0.05; //???
    vec3 vectorSS = vec3(endPosSS.xyz - startPosSS.xyz)/stepsCount;

    // Init vars for cycle
    vec2 samplePos = vec2(0.0, 0.0);// texcoord for the depth and color
    float sampleDepth = 0.0;        // depth from texture
    float currentDepthSS = 0.0;     // current depth calculated with reflection vector in screen space
    float currentDepth = 0.0;       // current depth calculated with reflection vector
    float deltaD = 0.0;
    vec4 color = vec4(0.0, 0.0, 0.0, 0.0);
    for (int i = 1; i < stepsCount; i++)
        {
        samplePos = (startPosSS.xy + vectorSS.xy*i);
        currentDepthSS = startPosSS.z + vectorSS.z*i;
        currentDepth = linearizeDepth(currentDepthSS);
        sampleDepth = linearizeDepth( texture(depth, samplePos).r);
        deltaD = currentDepth - sampleDepth;
        if ( deltaD > 0 && deltaD < maxDelta * currentDepthSS)
            {
            color = texture(albedo, samplePos);
            //color=vec4(vectorSS*100.0, 0.0);
            //color *= fade * (1.0 - float(i) / float(stepsCount));
            break;
            }
        }
    return color;
    }



void main()
    {
    //float gloss = texture(color_tex, uv).a;
    //view space normal, it's a floating point tex,
    //normalized before writing, ready to use
    vec4 normal_map= texture(normal_tex, uv);
    float gloss=normal_map.a;
    vec3 N = unpack_normal_octahedron(normal_map.xy);
    //hardware depth
    float D = texture(depth_tex, uv).r;

    //view pos in camera space
    vec4 P = trans_apiclip_of_camera_to_apiview_of_camera * vec4( uv.xy,  D, 1.0);
    P.xyz /= P.w;
    //view direction
    vec3 V = normalize(P.xyz);
    // Reflection vector in camera space
    vec3 R = normalize(reflect(V, N)) * zFar * rayLength;

    float co=abs(dot(-V, N));
    vec4 final=raytrace(P.xyz, P.xyz + R,
                       trans_apiview_of_camera_to_apiclip_of_camera,
                       final_light, depth_tex);

    gl_FragData[0] =final*co*gloss;
    //gl_FragData[0] =vec4(co,co,co, 1.0);
    }

