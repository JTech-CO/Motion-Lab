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

float curlNoise(vec2 p) {
    float eps = 0.001;
    float n1 = noise(p + vec2(eps, 0.0));
    float n2 = noise(p - vec2(eps, 0.0));
    float n3 = noise(p + vec2(0.0, eps));
    float n4 = noise(p - vec2(0.0, eps));
    return (n1 - n2) - (n3 - n4);
}

float octogonPrismSDF(vec3 p, float r, float h) {
    vec3 k = vec3(-0.9238795325, 0.3826834323, 0.4142135623);
    p = abs(p);
    p.xy -= 2.0 * min(dot(vec2(k.x, k.y), p.xy), 0.0) * vec2(k.x, k.y);
    p.xy -= 2.0 * min(dot(vec2(-k.x, k.y), p.xy), 0.0) * vec2(-k.x, k.y);
    p.xy -= vec2(clamp(p.x, -k.z * r, k.z * r), r);
    vec2 d = vec2(length(p.xy) * sign(p.y), p.z - h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

vec3 spectral_gems(float x) {
    return clamp(1.0 - abs(vec3(4.0 * (x - 0.75), 4.0 * (x - 0.5), 4.0 * (x - 0.25))), 0.0, 1.0);
}

float ior2f0(float ior) {
    return (ior - 1.0) * (ior - 1.0) / ((ior + 1.0) * (ior + 1.0));
}

float raymarchDispersion(vec2 uv, float t) {
    vec3 ro = vec3(0.0, 0.0, 3.0);
    vec3 rd = normalize(vec3(uv, -1.5));
    
    float tMax = 10.0;
    float t = 0.0;
    float stepSize = 0.08;
    vec3 color = vec3(0.0);
    
    for (int i = 0; i < 40; i++) {
        vec3 p = ro + rd * t;
        p.xz *= mat2(cos(t * 0.3), -sin(t * 0.3), sin(t * 0.3), cos(t * 0.3));
        
        float d = octogonPrismSDF(p, 0.6, 0.8);
        
        if (d < 0.01) {
            float wavelength = fract(t * 0.25 + p.y * 0.15);
            vec3 spectral = spectral_gems(wavelength);
            
            float noiseVal = curlNoise(p.xy * 2.0 + t * 0.5);
            float intensity = 1.0 - smoothstep(0.0, 0.02, d);
            intensity *= 0.8 + 0.2 * noiseVal;
            
            color += spectral * intensity * 0.15;
            break;
        }
        
        t += stepSize;
        if (t > tMax) break;
    }
    
    return length(color);
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    float dispersion = raymarchDispersion(uv, uTime);
    
    vec3 bg = vec3(0.05, 0.03, 0.08) + 0.15 * smoothstep(0.0, 1.5, length(uv));
    vec3 color = bg + vec3(dispersion);
    
    color = pow(color, vec3(0.85));
    color = min(color, 1.0);
    
    gl_FragColor = vec4(color, 1.0);
}