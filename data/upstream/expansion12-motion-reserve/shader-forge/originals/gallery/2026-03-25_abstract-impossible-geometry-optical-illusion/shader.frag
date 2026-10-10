uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define TAU 6.28318530718
#define PI 3.14159265359

// Simple hash for pseudo-random
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// 2D rotation
mat2 rot(float a) {
    float s = sin(a);
    float c = cos(a);
    return mat2(c, -s, s, c);
}

// Smooth minimum
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Octogon SDF in 2D
float oct2D(in vec2 p, float r) {
    vec2 k = vec2(-0.9238795325, 0.3826834323);
    p = abs(p);
    p.xy -= 2.0 * min(dot(p.xy, vec2(k.x, k.y)), 0.0) * vec2(k.x, k.y);
    p.xy -= 2.0 * min(dot(p.xy, vec2(-k.x, k.y)), 0.0) * vec2(-k.x, k.y);
    return length(max(abs(p) - r, 0.0));
}

// Domain repetition + folding
vec3 fold(vec3 p) {
    p.xy = abs(p.xy);
    p.x = p.x - 2.0 * max(dot(p.xy, vec2(0.866025, 0.5)), 0.0) * 0.866025;
    p.y = p.y - 2.0 * max(dot(p.xy, vec2(-0.866025, 0.5)), 0.0) * -0.866025;
    return p;
}

// Main SDF function for impossible geometry
float map(vec3 p) {
    vec3 q = p;
    q = fold(q);
    
    float d1 = oct2D(q.xy, 0.6) + abs(q.z) * 0.3;
    float d2 = length(q.xy - vec2(0.4, 0.4)) - 0.2;
    float d3 = length(q.xy + vec2(0.4, -0.4)) - 0.2;
    
    return smin(d1, smin(d2, d3, 0.1), 0.05);
}

// Raymarching
vec3 raymarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    vec3 col = vec3(0.0);
    
    // Background gradient
    float bg = smoothstep(0.0, 1.0, rd.y + 0.3);
    col = mix(vec3(0.02, 0.01, 0.05), vec3(0.05, 0.02, 0.08), bg);
    
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        
        if (d < 0.001) {
            // Surface normal approximation
            vec2 e = vec2(0.001, 0.0);
            vec3 n = normalize(vec3(
                map(p + e.xyy) - map(p - e.xyy),
                map(p + e.yxy) - map(p - e.yxy),
                map(p + e.yyx) - map(p - e.yyx)
            ));
            
            // Lighting
            vec3 lightDir = normalize(vec3(0.5, 0.7, 0.4));
            float diff = max(dot(n, lightDir), 0.0);
            float spec = pow(max(dot(reflect(-lightDir, n), -rd), 0.0), 32.0);
            
            // Fresnel
            float fresnel = pow(1.0 - dot(n, -rd), 3.0);
            
            // Base color with interference pattern
            vec3 base = vec3(
                sin(p.x * 4.0 + uTime) * 0.5 + 0.5,
                sin(p.y * 4.0 + uTime * 0.7) * 0.5 + 0.5,
                sin(p.z * 4.0 + uTime * 0.3) * 0.5 + 0.5
            );
            
            // Neon colors
            vec3 neon = vec3(0.1, 1.0, 0.9) * diff + vec3(1.0, 0.5, 0.2) * spec + vec3(0.9, 0.2, 1.0) * fresnel;
            
            // Distance fade
            float alpha = exp(-t * 0.2);
            
            col = mix(col, base * neon * alpha, 0.8);
            break;
        }
        
        t += d;
        if (t > 10.0) break;
    }
    
    // Vignette
    float vignette = smoothstep(1.0, 0.2, length(vUv - 0.5));
    col *= vignette;
    
    return col;
}

void main() {
    // Normalize UVs to -1..1
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    // Camera setup
    vec3 ro = vec3(0.0, 0.0, -2.5);
    vec3 rd = normalize(vec3(uv, 1.0));
    
    // Rotate camera
    float camRot = uTime * 0.2;
    rd.xy = rot(camRot) * rd.xy;
    
    // Kaleidoscopic effect on camera
    rd.xy = abs(rd.xy) - vec2(0.5);
    rd.xy = rd.xy * 2.0;
    
    vec3 col = raymarch(ro, rd);
    
    // Contrast and color enhancement
    col = pow(col, vec3(1.2));
    col = mix(col, vec3(0.1, 0.1, 0.2), 0.1);
    
    gl_FragColor = vec4(col, 1.0);
}