uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple hash and noise
float hash(float n) { return fract(sin(n) * 43758.5453123); }
float noise(vec2 p) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    float a = hash(ip.x + ip.y * 57.0);
    float b = hash(ip.x + 1.0 + ip.y * 57.0);
    float c = hash(ip.x + (ip.y + 1.0) * 57.0);
    float d = hash(ip.x + 1.0 + (ip.y + 1.0) * 57.0);
    vec2 u = fp * fp * (3.0 - 2.0 * fp);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 5; i++) {
        f += w * noise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

float map(vec3 p) {
    float t = uTime * 0.4;
    vec3 q = p;
    float d = length(q.xy) - 0.3 - 0.1 * sin(t * 0.7 + q.z * 0.5);
    q.xy *= mat2(0.866, -0.5, 0.5, 0.866);
    d = min(d, length(q.xy) - 0.2 - 0.15 * cos(t * 0.9 + q.z * 0.4));
    return d;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        map(p + e.xyy) - map(p - e.xyy),
        map(p + e.yxy) - map(p - e.yxy),
        map(p + e.yyx) - map(p - e.yyx)
    ));
}

vec3 waterPalette(float x) {
    return pow(vec3(0.1, 0.7, 0.8), vec3(4.0 * clamp(1.0 - x, 0.0, 1.0)));
}

void main() {
    vec2 uv = (vUv - 0.5) * 2.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 ro = vec3(0.0, 0.0, 3.0);
    vec3 rd = normalize(vec3(uv, -1.5));
    
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        if (map(p) < 0.001 || t > 10.0) break;
        t += map(p) * 0.8;
    }
    
    vec3 col = vec3(0.03, 0.05, 0.1) * (1.0 - t * 0.1);
    
    if (t < 10.0) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        vec3 lightDir = normalize(vec3(0.7, 0.3, -1.0));
        vec3 viewDir = normalize(ro - p);
        vec3 halfDir = normalize(lightDir + viewDir);
        
        float diff = max(dot(n, lightDir), 0.0);
        float spec = pow(max(dot(n, halfDir), 0.0), 64.0);
        float fresnel = pow(1.0 - max(dot(n, viewDir), 0.0), 4.0);
        
        float ambient = 0.3 + 0.2 * fbm(p.xz * 0.5);
        
        vec3 jellyColor = vec3(0.1, 0.8, 0.9);
        vec3 bioluminescence = jellyColor * 2.0 * (0.5 + 0.5 * sin(p.x * 6.0 + uTime * 2.0 + p.z * 4.0));
        
        col = waterPalette(1.0 - t * 0.1);
        col += jellyColor * diff * 0.7;
        col += bioluminescence * 0.8;
        col += vec3(1.0) * spec * 0.6;
        col += jellyColor * fresnel * 0.5;
        col += vec3(0.02, 0.1, 0.2) * ambient;
    }
    
    float vignette = 1.0 - length(uv) * 0.6;
    col *= vignette;
    
    col = pow(col, vec3(1.2));
    
    gl_FragColor = vec4(col, 1.0);
}