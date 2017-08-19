//GLSL
#version 140
uniform sampler2D compose;
uniform float blur;

in vec2 uv;

void main()
    {
    vec2 pixel = vec2(1.0, 1.0)/textureSize(compose, 0).xy;
    vec2 depth_sharp=pixel*blur;

    vec4 base_tex=texture(compose, uv);

    vec4 out_tex= texture(compose, uv);
    //Hardcoded blur
    out_tex += texture(compose, uv+vec2(-0.326212,-0.405805)*depth_sharp);
    out_tex += texture(compose, uv+ vec2(-0.840144, -0.073580)*depth_sharp);
    out_tex += texture(compose, uv+vec2(-0.695914,0.457137)*depth_sharp);
    out_tex += texture(compose, uv+vec2(-0.203345,0.620716)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.962340,-0.194983)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.473434,-0.480026)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.519456,0.767022)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.185461,-0.893124)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.507431,0.064425)*depth_sharp);
    out_tex += texture(compose, uv+vec2(0.896420,0.412458)*depth_sharp);
    out_tex += texture(compose, uv+vec2(-0.321940,-0.932615)*depth_sharp);
    out_tex += texture(compose, uv+vec2(-0.791559,-0.597705)*depth_sharp);
    out_tex/=13.0;

    gl_FragData[0] = vec4(mix(out_tex.rgb, base_tex.rgb, base_tex.a), 1.0);
    }

