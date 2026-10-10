uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define N(x,y,z) normalize(vec3(x,y,z))
#define GYR(p) (sin(p.x)*cos(p.y) + sin(p.y)*cos(p.z) + sin(p.z)*cos(p.x))

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
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

float fbm(vec3 p) {
    float result = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) {
        p.z += result * 0.1;
        result += abs(GYR(p / a)) * a;
        a *= 0.5;
    }
    return result;
}

float rm(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = GYR(p + vec3(0.0, 0.0, uTime * 0.4)) * 0.5 + fbm(p * 1.5) * 0.2;
        if (abs(d) < 0.001 * t) return t;
        t += d * 0.8;
        if (t > 10.0) return 10.0;
    }
    return 10.0;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.01, 0.0);
    float dx = fbm(p + vec3(e.x, e.y, e.y)) - fbm(p - vec3(e.x, e.y, e.y));
    float dy = fbm(p + vec3(e.y, e.x, e.y)) - fbm(p - vec3(e.y, e.x, e.y));
    float dz = fbm(p + vec3(e.y, e.y, e.x)) - fbm(p - vec3(e.y, e.y, e.x));
    return N(dx, dy, dz);
}

vec3 shade(vec3 p, vec3 n, vec3 rd) {
    vec3 col = 0.5 + 0.5 * cos(6.28318 * (n * 2.0 + uTime * 0.3) + vec3(0.0, 1.0, 2.0));
    col = mix(vec3(0.02), col, 0.98);
    col += 0.3 * pow(1.0 - dot(n, -rd), 5.0);
    return clamp(col, 0.0, 1.0);
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 ro = vec3(0.0, 0.0, 3.0);
    vec3 rd = normalize(vec3(uv, -1.5));
    
    float t = rm(ro, rd);
    vec3 col = vec3(0.02);
    
    if (t < 9.9) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        col = shade(p, n, rd);
    }
    
    gl_FragColor = vec4(col, 1.0);
}