uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) { return fract(sin(dot(p.xy, vec2(12.9898, 78.233))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p); vec2 f = fract(p);
    float a = hash(i); float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0)); float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
    float f = 0.0; float a = 0.5;
    for (int i = 0; i < 4; i++) {
        f += a * noise(p); p *= 2.0; a *= 0.5;
    }
    return f;
}
float map(vec3 p) {
    float t = uTime * 0.3;
    float r = length(p.xz);
    float h = p.y + 1.0;
    float wave = sin(p.x * 2.0 + t) * 0.1 + cos(p.z * 1.5 - t * 0.8) * 0.1;
    float jelly = exp(-pow(r * 2.0, 2.0)) * (1.0 - exp(-pow(h * 1.5, 2.0))) + wave * 0.5;
    return jelly;
}
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(map(p + e.xyy) - map(p - e.xyy), map(p + e.yxy) - map(p - e.yxy), map(p + e.yyx) - map(p - e.yyx)));
}
float fresnel(vec3 v, vec3 n, float base) {
    return base + (1.0 - base) * pow(1.0 - dot(v, n), 5.0);
}

void main() {
    vec2 uv = vUv;
    uv = (uv - 0.5) * uResolution / min(uResolution.x, uResolution.y);
    
    vec3 ro = vec3(0.0, 0.0, -3.0);
    vec3 rd = normalize(vec3(uv, 1.5));
    
    float t = 0.0;
    float alpha = 0.0;
    vec3 totalColor = vec3(0.05, 0.1, 0.15);
    
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        float dens = clamp(1.0 - d * 2.0, 0.0, 1.0);
        
        if (dens > 0.01) {
            vec3 n = calcNormal(p);
            vec3 lightDir = normalize(vec3(0.5, 1.0, 1.0));
            float diff = max(dot(n, lightDir), 0.0);
            float spec = pow(max(dot(reflect(-lightDir, n), -rd), 0.0), 32.0);
            float fres = fresnel(-rd, n, 0.2);
            
            vec3 jellyColor = vec3(0.1, 0.9, 0.7) * diff + vec3(0.9, 0.95, 1.0) * spec;
            jellyColor += vec3(0.1, 0.3, 0.5) * fres * 0.5;
            
            float glow = exp(-pow(length(p.xz) * 1.5 - 0.5, 2.0)) * 0.5;
            jellyColor += vec3(0.2, 0.8, 0.6) * glow;
            
            vec3 plankton = vec3(0.9, 1.0, 0.8) * smoothstep(0.0, 0.05, hash(p.xz * 20.0) - 0.98);
            jellyColor += plankton * 0.5;
            
            vec3 waterColor = vec3(0.02, 0.1, 0.15) + vec3(0.01, 0.05, 0.1) * (1.0 - exp(-t * 0.5));
            totalColor = mix(totalColor, jellyColor, dens * 0.15);
            alpha += dens * 0.08;
        }
        
        t += 0.05;
        if (alpha > 0.95) break;
    }
    
    // Deep ocean fog
    vec3 sky = vec3(0.0, 0.05, 0.1) * (1.0 - exp(-t * 0.2));
    vec3 finalColor = mix(totalColor, sky, exp(-alpha));
    
    gl_FragColor = vec4(finalColor, 1.0);
}