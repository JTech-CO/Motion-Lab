precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define PI 3.141592653589793

vec3 rotate(vec2 uv, float a) {
    float c = cos(a), s = sin(a);
    return vec3(uv.x * c - uv.y * s, uv.x * s + uv.y * c, uv.x * uv.x + uv.y * uv.y);
}

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (12.9898 + 78.233 * p.x));
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float f = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) {
        f += a * noise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return f;
}

float map(vec3 p) {
    float h = p.y + 0.5;
    vec2 q = p.xz * 0.15;
    float terrain = fbm(q) * 0.4 + fbm(q * 2.0) * 0.2;
    h -= terrain * (1.0 - smoothstep(0.0, 2.0, p.y));
    return h;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.01, 0.0);
    return normalize(vec3(map(p + e.xyy) - map(p - e.xyy),
                          map(p + e.yxy) - map(p - e.yxy),
                          map(p + e.yyx) - map(p - e.yyx)));
}

vec3 heatmap(float v) {
    vec3 r = v * 2.1 - vec3(1.8, 1.14, 0.3);
    return 1.0 - r * r;
}

vec3 fire(float x) {
    return vec3(1.0, 0.25, 0.0625) * exp(4.0 * x - 1.0);
}

void main() {
    vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution.xy) / min(uResolution.x, uResolution.y);
    
    vec3 ro = vec3(0.0, 2.5, -5.0 + uTime * 0.3);
    vec3 rd = normalize(vec3(uv, 1.5));
    
    float t = 0.0;
    vec3 col = vec3(0.05, 0.05, 0.1);
    
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + t * rd;
        float h = map(p);
        
        if (h < 0.01) {
            vec3 n = calcNormal(p);
            vec3 l = normalize(vec3(-0.5, 0.4, 0.3));
            float diff = max(0.0, dot(n, l));
            float spec = pow(max(0.0, dot(reflect(-l, n), -rd)), 32.0);
            
            float lava = smoothstep(0.0, 0.2, -p.y) * (0.5 + 0.5 * fbm(p.xz * 0.2 + uTime * 0.2));
            vec3 lavaColor = mix(fire(lava), heatmap(lava), 0.7);
            
            col = vec3(0.15, 0.1, 0.08) * (1.0 - smoothstep(0.0, 3.0, -p.y)) + 
                  vec3(0.9, 0.4, 0.1) * lava * 1.5;
            col *= (0.3 + 0.7 * diff) + 0.5 * spec;
            col += vec3(0.9, 0.6, 0.2) * smoothstep(0.0, 0.3, -p.y) * 0.5;
            break;
        }
        
        t += max(0.1, h);
        if (t > 30.0) break;
    }
    
    // Volumetric smoke
    float smoke = 0.0;
    float smokeT = 0.0;
    for (int i = 0; i < 16; i++) {
        vec3 sp = ro + rd * (t * 0.2 + float(i) * 0.6);
        float density = 1.0 - smoothstep(0.0, 2.0, sp.y);
        density *= 0.5 + 0.5 * fbm(sp.xz * 0.3 + uTime * 0.1);
        density *= smoothstep(0.5, 2.0, sp.y);
        smoke += density * 0.15 * (1.0 - smokeT);
        smokeT += density * 0.15;
    }
    col *= 1.0 - smoke * 0.8;
    col += vec3(0.4, 0.4, 0.5) * smoke * 0.3;
    
    // Ash particles
    float ash = 0.0;
    for (int i = 0; i < 8; i++) {
        vec2 ap = vec2(float(i) * 13.7, uTime * 0.5 + float(i) * 0.3);
        float d = length(uv - (rotate(ap, uTime * 0.2).xy * 0.3));
        ash += 0.05 / (d * d + 0.1);
    }
    col += vec3(0.8, 0.6, 0.4) * ash * 0.2;
    
    // Heat bloom
    float bloom = length(uv) * 0.5;
    col += vec3(0.9, 0.3, 0.1) * exp(-bloom * 2.0) * 0.2;
    
    gl_FragColor = vec4(col, 1.0);
}