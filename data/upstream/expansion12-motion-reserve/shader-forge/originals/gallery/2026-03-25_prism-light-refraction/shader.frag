uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (1.0 + uTime * 0.2));
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
    float v = 0.0;
    float a = 0.5;
    vec2 shift = vec2(100.0);
    mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = rot * p * 2.0 + shift;
        a *= 0.5;
    }
    return v;
}

vec3 palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557);
    return a + b * cos(6.28318 * (c * t + d + uTime * 0.1));
}

void main() {
    vec2 uv = vUv;
    uv *= uResolution / min(uResolution.x, uResolution.y);
    
    vec2 p = uv * 2.0 - 1.0;
    float r = length(p);
    float theta = atan(p.y, p.x);
    
    float a = fbm(p * 1.5 + uTime * 0.2);
    float b = fbm(p * 2.0 - uTime * 0.3);
    float c = fbm(p * 3.0 + uTime * 0.1);
    
    float spectrum = a * 0.6 + b * 0.3 + c * 0.1;
    vec3 color = palette(spectrum);
    
    float ring = sin(r * 8.0 - uTime * 2.0) * 0.05;
    ring += sin(r * 16.0 - uTime * 3.0) * 0.025;
    
    float fresnel = pow(1.0 - dot(normalize(vec3(p, 1.0)), vec3(0.0, 0.0, 1.0)), 3.0);
    
    color += ring * vec3(1.0, 0.8, 0.6) * 0.5;
    color += fresnel * vec3(0.8, 0.9, 1.0) * 0.7;
    
    color = mix(color, vec3(0.0), exp2(-r * 2.0));
    
    gl_FragColor = vec4(color, 1.0);
}