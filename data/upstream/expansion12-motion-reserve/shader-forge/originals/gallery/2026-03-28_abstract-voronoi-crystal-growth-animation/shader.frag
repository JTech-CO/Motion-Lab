uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

vec2 random2(vec2 p) {
    return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
}

vec3 voronoi(vec2 uv, float time) {
    vec2 i_uv = floor(uv);
    vec2 f_uv = fract(uv);
    vec3 rta = vec3(0.0, 0.0, 10.0);
    
    for (float j = -1.0; j <= 1.0; j += 1.0) {
        for (float i = -1.0; i <= 1.0; i += 1.0) {
            vec2 neighbor = vec2(i, j);
            vec2 point = random2(i_uv + neighbor);
            point = 0.5 + 0.5 * sin(time + 6.2831853 * point);
            vec2 diff = neighbor + point - f_uv;
            float dist = length(diff);
            
            if (dist < rta.z) {
                rta.xy = point;
                rta.z = dist;
            }
        }
    }
    return rta;
}

vec3 colorFromVoronoi(vec3 v) {
    float d = v.z;
    vec2 p = v.xy;
    
    // Base color from cell position
    vec3 col = 0.5 + 0.5 * sin(6.2831853 * (p.xyx + vec3(0.0, 0.3, 0.6)) + uTime * 0.5);
    
    // Add crystalline rings
    float rings = 0.5 + 0.5 * sin(40.0 * d - uTime);
    col += vec3(rings) * 0.3;
    
    // Edge glow
    float edge = smoothstep(0.02, 0.0, d);
    col += vec3(1.0) * edge * 0.4;
    
    // Soft contrast boost
    col = pow(col, vec3(0.85)) * 1.2;
    
    return col;
}

void main() {
    vec2 uv = vUv;
    uv = uv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 v = voronoi(uv * 2.0, uTime);
    vec3 col = colorFromVoronoi(v);
    
    gl_FragColor = vec4(col, 1.0);
}