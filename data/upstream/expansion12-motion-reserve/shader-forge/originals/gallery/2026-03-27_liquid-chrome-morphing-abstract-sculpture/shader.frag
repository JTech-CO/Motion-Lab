uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float gradNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    float v = mix(a, b, u.x);
    float w = mix(c, d, u.x);
    float gradX = (b - a) * (6.0 * f.x * (1.0 - f.x)) * (v - w) + (w - v);
    float gradY = (c - a) * (6.0 * f.y * (1.0 - f.y)) * (w - v) + (w - v);
    return gradX + gradY;
}

vec3 curlNoise(vec2 uv, float t) {
    float eps = 0.001;
    float nx0 = gradNoise(uv - vec2(eps, 0.0));
    float nx1 = gradNoise(uv + vec2(eps, 0.0));
    float ny0 = gradNoise(uv - vec2(0.0, eps));
    float ny1 = gradNoise(uv + vec2(0.0, eps));
    float nz = (nx1 - nx0 - ny1 + ny0) / (4.0 * eps);
    vec2 curlXY = vec2(ny1 - ny0, -(nx1 - nx0)) / (2.0 * eps);
    return vec3(curlXY, nz * 0.5 + 0.5);
}

vec3 warp(vec3 p, float t) {
    vec3 curl = curlNoise(p.xy * 0.5 + t * 0.3, t);
    p.xy += curl.xy * 0.35;
    p.z += curl.z * 0.2;
    return p;
}

vec3 chromeColor(vec3 p, float t) {
    vec3 base = vec3(0.06, 0.06, 0.08);
    vec3 mid = mix(vec3(0.35, 0.38, 0.42), vec3(0.85, 0.88, 0.92), 
                   0.5 + 0.5 * sin(t * 0.8 + p.x * 3.0));
    float spec = pow(1.0 - dot(normalize(vec3(p.xy, 1.0)), vec3(0.0, 0.0, 1.0)), 5.0);
    vec3 highlight = vec3(1.0) * spec * 0.7;
    float irid = 0.5 + 0.5 * sin(p.x * 6.0 + t * 2.0 + p.z * 4.0);
    return mix(base, mid, smoothstep(0.0, 1.0, length(p.xy) * 0.6)) + highlight + vec3(irid) * 0.15;
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    vec3 pos = vec3(uv, 0.0);
    float t = uTime * 0.4;
    
    for (int i = 0; i < 4; i++) {
        pos = warp(pos, t + float(i) * 0.15);
    }
    
    float dist = length(pos.xy);
    float density = smoothstep(0.8, 0.2, dist);
    density = smoothstep(0.0, 1.0, density * 1.2);
    
    vec3 color = chromeColor(pos, t);
    color = mix(color * 0.9, vec3(0.98), density * 0.6);
    
    gl_FragColor = vec4(color, 1.0);
}