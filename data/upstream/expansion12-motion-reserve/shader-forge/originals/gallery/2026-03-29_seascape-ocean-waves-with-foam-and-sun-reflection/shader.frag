precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// --- Utilities ---
float hash1(float p) {
    float h = dot(vec2(p), vec2(127.1, 311.7));
    return fract(sin(h) * 43758.5453123);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash1(i.x + i.y * 57.0);
    float b = hash1(i.x + 1.0 + i.y * 57.0);
    float c = hash1(i.x + (i.y + 1.0) * 57.0);
    float d = hash1(i.x + 1.0 + (i.y + 1.0) * 57.0);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float val = 0.0;
    float amp = 0.5;
    mat2 octave_m = mat2(1.6, 1.2, -1.2, 1.6);
    for (int i = 0; i < 4; i++) {
        val += amp * noise(p);
        p = octave_m * p;
        amp *= 0.5;
    }
    return val;
}

// --- Sea Functions ---
const float SEA_HEIGHT = 0.6;
const float SEA_CHOPPY = 4.0;
const float SEA_FREQ = 0.16;
const vec3 SEA_BASE = vec3(0.0, 0.09, 0.18);
const vec3 SEA_WATER_COLOR = vec3(0.8, 0.9, 0.6) * 0.6;

float seaHeight(vec2 p) {
    vec2 q = p;
    q += noise(q + uTime * 0.1) * SEA_CHOPPY * 0.1;
    float h = fbm(q * SEA_FREQ) * SEA_HEIGHT;
    return h;
}

vec3 getSky(vec3 dir) {
    vec3 skyCol1 = vec3(0.1, 0.3, 0.6);
    vec3 skyCol2 = vec3(0.6, 0.8, 1.0);
    return mix(skyCol1, skyCol2, clamp(dir.y * 1.5 + 0.5, 0.0, 1.0));
}

vec3 getSun(vec3 dir) {
    vec3 sunDir = normalize(vec3(0.2, 0.3, 1.0));
    float sunDot = max(dot(dir, sunDir), 0.0);
    vec3 sunCol = vec3(1.0, 0.9, 0.7);
    return sunCol * pow(sunDot, 200.0) * 2.0;
}

void main() {
    vec2 uv = (vUv * 2.0 - 1.0);
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 eye = vec3(0.0, 2.0, 0.0);
    vec3 dir = normalize(vec3(uv, -1.5));
    
    // Raymarch
    float t = 0.1;
    float depth = 0.0;
    vec3 col = getSky(dir);
    
    for (int i = 0; i < 12; i++) {
        t += 0.3;
        vec3 pos = eye + dir * t;
        float h = seaHeight(pos.xz);
        depth = t * dir.z;
        
        if (pos.y < h) {
            // Compute normal via finite differences
            float eps = 0.002;
            float hL = seaHeight(pos.xz - vec2(eps, 0.0));
            float hR = seaHeight(pos.xz + vec2(eps, 0.0));
            float hD = seaHeight(pos.xz - vec2(0.0, eps));
            float hU = seaHeight(pos.xz + vec2(0.0, eps));
            vec3 n = normalize(vec3(hL - hR, 2.0 * eps, hD - hU));
            
            // Fresnel
            float fresnel = pow(1.0 - dot(-dir, n), 4.0);
            
            // Sky reflection
            vec3 reflDir = reflect(dir, n);
            vec3 skyColor = getSky(reflDir);
            
            // Sun reflection
            vec3 sunColor = getSun(reflDir);
            
            // Sea base color with depth fading
            vec3 seaColor = SEA_BASE + SEA_WATER_COLOR * (1.0 - smoothstep(0.0, 1.0, depth * 0.3));
            
            // Foam (gradient-based)
            float heightGradient = length(vec2(hR - hL, hU - hD)) / (2.0 * eps);
            float foam = smoothstep(0.8, 1.0, heightGradient * 2.0);
            vec3 foamColor = vec3(1.0, 0.95, 0.9) * foam * 0.8;
            
            // Final blend
            vec3 waterColor = mix(seaColor, skyColor + sunColor * 2.0, fresnel);
            col = waterColor + foamColor;
            break;
        }
    }
    
    // Sky fill for rays that miss sea
    if (t > 10.0) {
        col = getSky(dir);
    }
    
    gl_FragColor = vec4(col, 1.0);
}