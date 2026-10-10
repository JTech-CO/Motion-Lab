#ifdef GL_ES
precision highp float;
#endif

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Utilities
float hash(float n) { return fract(sin(n) * 43758.5453); }
float noise(vec2 x) {
    vec2 p = floor(x);
    vec2 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(dot(p, vec2(1.0, 2.0))), hash(dot(p + vec2(1.0, 2.0), vec2(1.0, 2.0))), f.x),
               mix(hash(dot(p + vec2(0.0, 1.0), vec2(1.0, 2.0))), hash(dot(p + vec2(1.0, 1.0), vec2(1.0, 2.0))), f.x), f.y);
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
    float d = 1e5;
    float h = 1.5 * sin(p.x * 0.1) * cos(p.z * 0.1);
    p.y -= h;
    float bx = mod(p.x, 10.0) - 5.0;
    float bz = mod(p.z, 10.0) - 5.0;
    float dist = max(abs(bx), abs(bz));
    d = min(d, dist - 1.0);
    return d;
}
float raymarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        float d = map(ro + rd * t);
        if (d < 0.01 || t > 40.0) break;
        t += d;
    }
    return t;
}
vec3 getNormal(vec3 p) {
    vec2 e = vec2(0.01, 0.0);
    return normalize(vec3(map(p + e.xyy) - map(p - e.xyy),
                          map(p + e.yxy) - map(p - e.yxy),
                          map(p + e.yyx) - map(p - e.yyx)));
}

void main() {
    vec2 uv = (vUv - 0.5) * uResolution / min(uResolution.x, uResolution.y);
    vec2 uv0 = vUv;

    // Camera
    vec3 ro = vec3(0.0, 3.0, -6.0);
    vec3 rd = normalize(vec3(uv.x, uv.y, 1.0));

    // Sky
    vec3 col = vec3(0.05, 0.05, 0.1);
    float t = raymarch(ro, rd);
    if (t < 40.0) {
        vec3 p = ro + rd * t;
        vec3 n = getNormal(p);
        vec3 lightDir = normalize(vec3(0.5, 1.0, -0.3));
        float diff = max(dot(n, lightDir), 0.0);
        float spec = pow(max(dot(reflect(-lightDir, n), -rd), 0.0), 32.0);
        vec3 neon = vec3(0.0, 1.0, 1.0) * smoothstep(-0.2, 0.2, p.x) * smoothstep(-0.2, 0.2, p.z);
        col = vec3(0.1, 0.1, 0.2) * diff + vec3(1.0, 0.0, 1.0) * neon + spec * vec3(0.8, 1.0, 1.0);
        col += vec3(0.2, 0.3, 0.5) * pow(1.0 - t / 40.0, 2.0); // Fog
    }

    // Rain
    float rain = 0.0;
    for (int i = 0; i < 5; i++) {
        float y = mod(uTime * 30.0 + float(i) * 7.3, 20.0);
        float x = mod(float(i) * 13.7, 20.0) - 10.0;
        float z = mod(float(i) * 17.1, 20.0) - 10.0;
        float dist = length(uv.x - x) + abs(uv.y * 0.3 - y * 0.05);
        rain += 0.03 / (dist * dist + 0.1);
    }
    col += vec3(0.6, 0.7, 1.0) * rain * 0.5;

    // Ground reflection (fake)
    vec2 ruv = vec2(uv.x, -uv.y);
    float rDist = raymarch(ro + vec3(0.0, 6.0, 0.0), vec3(ruv.x, ruv.y, -1.0));
    if (rDist < 40.0) {
        vec3 rp = ro + vec3(0.0, 6.0, 0.0) + vec3(ruv.x, ruv.y, -1.0) * rDist;
        vec3 rn = getNormal(rp);
        vec3 rLightDir = normalize(vec3(0.5, 1.0, -0.3));
        float rDiff = max(dot(rn, rLightDir), 0.0);
        vec3 rNeon = vec3(0.0, 1.0, 1.0) * smoothstep(-0.2, 0.2, rp.x) * smoothstep(-0.2, 0.2, rp.z);
        vec3 rCol = vec3(0.1, 0.1, 0.2) * rDiff + vec3(1.0, 0.0, 1.0) * rNeon;
        rCol += vec3(0.2, 0.3, 0.5) * pow(1.0 - rDist / 40.0, 2.0);
        col += rCol * 0.15 * (1.0 - smoothstep(0.0, 0.5, uv.y));
    }

    // Puddle ripples
    float ripples = 0.0;
    for (int i = 0; i < 3; i++) {
        float freq = float(i + 1) * 3.0;
        float amp = 0.02 / float(i + 1);
        ripples += amp * sin(uv.x * freq + uTime * 2.0 + uv.y * freq);
    }
    col += vec3(0.0, 0.3, 0.5) * ripples * smoothstep(-0.5, 0.5, uv.y) * 0.5;

    // Bloom (fake)
    col += vec3(1.0, 0.5, 1.0) * rain * 0.3;

    gl_FragColor = vec4(col, 1.0);
}