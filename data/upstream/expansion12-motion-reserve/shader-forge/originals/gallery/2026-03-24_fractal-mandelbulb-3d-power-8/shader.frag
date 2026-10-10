precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define MAX_STEPS 64
#define MAX_DIST 10.0
#define SURF_DIST 0.001
#define POWER 8.0

float hash(float n) { return fract(sin(n) * 43758.5453); }

float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    float n = p.x + p.y * 57.0 + 113.0 * p.z;
    return mix(mix(mix(hash(n + 0.0), hash(n + 1.0), f.x),
                   mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y),
               mix(mix(hash(n + 113.0), hash(n + 114.0), f.x),
                   mix(hash(n + 170.0), hash(n + 171.0), f.x), f.y), f.z);
}

float mandelbulbSDF(vec3 pos) {
    vec3 z = pos;
    float dr = 1.0;
    float r = 0.0;
    for (int i = 0; i < 8; i++) {
        r = length(z);
        if (r > 2.0) break;
        if (r > 0.0) {
            dr = pow(r, POWER - 1.0) * POWER * dr + 1.0;
            float theta = acos(z.z / r);
            float phi = atan(z.y, z.x);
            float r2 = pow(r, POWER);
            float theta2 = theta * POWER;
            float phi2 = phi * POWER;
            z = r2 * vec3(sin(theta2) * cos(phi2), sin(theta2) * sin(phi2), cos(theta2));
            z += pos;
        }
    }
    return 0.5 * log(r) * r / dr;
}

float raymarch(vec3 ro, vec3 rd) {
    float d = 0.0;
    for (int i = 0; i < MAX_STEPS; i++) {
        vec3 pos = ro + rd * d;
        float dist = mandelbulbSDF(pos);
        d += dist;
        if (dist < SURF_DIST || d > MAX_DIST) break;
    }
    return d;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        mandelbulbSDF(p + e.xyy) - mandelbulbSDF(p - e.xyy),
        mandelbulbSDF(p + e.yxy) - mandelbulbSDF(p - e.yxy),
        mandelbulbSDF(p + e.yyx) - mandelbulbSDF(p - e.yyx)
    ));
}

vec3 orbitTrap(vec3 p) {
    vec3 trap = p;
    float dist = length(p);
    for (int i = 0; i < 8; i++) {
        float r = length(trap);
        if (r > 2.0) break;
        if (r > 0.0) {
            float theta = acos(trap.z / r);
            float phi = atan(trap.y, trap.x);
            float r2 = pow(r, POWER);
            float theta2 = theta * POWER;
            float phi2 = phi * POWER;
            trap = r2 * vec3(sin(theta2) * cos(phi2), sin(theta2) * sin(phi2), cos(theta2));
            trap += p;
            dist = min(dist, length(trap));
        }
    }
    return vec3(dist);
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 ro = vec3(0.0, 0.0, -3.0);
    vec3 rd = normalize(vec3(uv, 1.5));
    
    // Camera orbit
    float camRot = uTime * 0.3;
    mat2 rot = mat2(cos(camRot), -sin(camRot), sin(camRot), cos(camRot));
    ro.xz *= rot;
    rd.xz *= rot;
    
    float d = raymarch(ro, rd);
    
    if (d > MAX_DIST - 0.1) {
        gl_FragColor = vec4(vec3(0.0), 1.0);
        return;
    }
    
    vec3 pos = ro + rd * d;
    vec3 normal = calcNormal(pos);
    
    // Lighting
    vec3 lightDir = normalize(vec3(0.5, 1.0, 1.0));
    vec3 viewDir = normalize(-rd);
    vec3 halfDir = normalize(lightDir + viewDir);
    
    float diff = max(dot(normal, lightDir), 0.0);
    float spec = pow(max(dot(normal, halfDir), 0.0), 64.0);
    float fresnel = pow(1.0 - max(dot(viewDir, normal), 0.0), 5.0);
    
    // Ambient occlusion approximation
    float ao = 1.0 - 0.5 * noise(pos * 5.0);
    
    // Orbit trap coloring
    vec3 trapColor = orbitTrap(pos);
    vec3 baseColor = vec3(0.1, 0.3, 0.6) + 0.4 * trapColor;
    baseColor = fract(baseColor + uTime * 0.2);
    baseColor = mix(baseColor, baseColor * 1.5, trapColor.y);
    
    // Emission from orbit trap
    float emission = clamp(trapColor.x * 2.0, 0.0, 1.0);
    
    // Final color
    vec3 color = baseColor * (0.2 + 0.8 * diff * ao) + vec3(0.8, 0.9, 1.0) * spec;
    color += baseColor * emission * 1.5;
    color += vec3(0.1, 0.2, 0.4) * fresnel * 0.8;
    
    // Glow effect
    float glow = 1.0 - clamp(d / 3.0, 0.0, 1.0);
    color += vec3(0.3, 0.5, 0.8) * glow * 0.5;
    
    gl_FragColor = vec4(color, 1.0);
}