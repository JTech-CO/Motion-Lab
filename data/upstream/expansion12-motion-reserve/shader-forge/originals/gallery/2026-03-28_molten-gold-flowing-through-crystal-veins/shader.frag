uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// 3D noise helper
float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    vec3 n = p.x + p.y * 57.0 + 113.0 * p.z;
    return mix(mix(mix(dot(fract(sin(n + 0.0) * 43758.5453), f - 0.5),
                       dot(fract(sin(n + 1.0) * 43758.5453), f - vec3(1.0, 0.0, 0.5)), f.x),
                   mix(dot(fract(sin(n + 2.0) * 43758.5453), f - vec3(0.0, 1.0, 0.5)),
                       dot(fract(sin(n + 3.0) * 43758.5453), f - vec3(1.0, 1.0, 0.5)), f.x), f.y);
}

float curlNoise(vec2 uv) {
    vec3 p = vec3(uv * 3.0, uTime * 0.4);
    float n1 = noise(p + vec3(0.0, 0.0, 0.0));
    float n2 = noise(p + vec3(1.0, 0.0, 0.0));
    float n3 = noise(p + vec3(0.0, 1.0, 0.0));
    float n4 = noise(p + vec3(0.0, 0.0, 1.0));
    return (n2 - n1) * 0.5 + (n4 - n3) * 0.5;
}

// Smooth minimum for metaball blending
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Hexagonal SDF
float hexSDF(vec2 p, float r) {
    vec3 n1 = normalize(vec3(2.618, 1.0, 0.0));
    p = abs(p / r);
    float a = dot(p, n1.xy);
    float b = dot(p, n1.yx);
    return max(a, b) - n1.x;
}

// Fluid SDF with time-varying warping
float fluidSDF(vec3 p, float t) {
    float flow = curlNoise(p.xy * 0.5) * 0.3;
    vec2 uv = p.xy + vec2(flow, flow * 0.5);
    
    // Hexagonal vein pattern
    float d1 = hexSDF(uv * 1.2, 0.4);
    
    // Organic blob distortion
    float blob = length(p.xy - vec2(sin(t * 0.7) * 0.5, cos(t * 0.5) * 0.5)) - 0.3;
    
    // Combine with smooth minimum
    float d = smin(d1, blob, 0.2);
    
    // Add third dimension variation
    d += sin(p.z * 3.0 + t) * 0.1;
    
    return d;
}

// Calculate normal
vec3 calcNormal(vec3 p, float t) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        fluidSDF(p + e.xyy, t) - fluidSDF(p - e.xyy, t),
        fluidSDF(p + e.yxy, t) - fluidSDF(p - e.yxy, t),
        fluidSDF(p + e.yyx, t) - fluidSDF(p - e.yyx, t)
    ));
}

// Gold material lighting
vec3 litGold(vec3 pos, vec3 normal, vec3 view) {
    // Gold IOR parameters from reference
    vec3 N = vec3(0.20152, 0.3483, 1.3654);
    vec3 K = vec3(3.1538, 2.4204, 1.7520);
    
    vec3 lightDir = normalize(vec3(0.5, 1.0, 1.0));
    vec3 halfDir = normalize(lightDir + view);
    
    // Diffuse (metallic base)
    float diff = max(dot(normal, lightDir), 0.0);
    
    // Specular
    float spec = pow(max(dot(normal, halfDir), 0.0), 60.0) * 1.5;
    
    // Fresnel
    float fresnel = pow(1.0 - max(dot(normal, view), 0.0), 3.0);
    
    // Gold colors
    vec3 baseGold = vec3(1.0, 0.8, 0.2);
    vec3 hotGold = vec3(0.95, 0.7, 0.1);
    
    // Compose
    vec3 color = baseGold * (diff * 0.6 + 0.2);
    color += hotGold * spec;
    color += hotGold * fresnel * 0.8;
    
    // Iridescence effect
    float irid = dot(normal, view) * 0.5 + 0.5;
    color += hotGold * sin(irid * 6.28 + uTime * 0.5) * 0.15;
    
    return color;
}

// Raymarch the scene
vec2 raymarch(vec2 uv) {
    vec3 ro = vec3(0.0, 0.0, 2.0);
    vec3 rd = normalize(vec3(uv, -1.5));
    
    float t = 0.0;
    float d;
    
    for (int i = 0; i < 48; i++) {
        vec3 p = ro + rd * t;
        d = fluidSDF(p, uTime);
        if (d < 0.001 || t > 3.0) break;
        t += d * 0.8;
    }
    
    return vec2(t, d);
}

void main() {
    // Normalize UVs
    vec2 uv = (vUv - 0.5) * 2.0;
    uv.x *= uResolution.x / uResolution.y;
    
    // Raymarch
    vec2 hit = raymarch(uv);
    float t = hit.x;
    float d = hit.y;
    
    vec3 color = vec3(0.05, 0.03, 0.01);
    
    if (d < 0.001) {
        vec3 ro = vec3(0.0, 0.0, 2.0);
        vec3 rd = normalize(vec3(uv, -1.5));
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p, uTime);
        vec3 viewDir = normalize(ro - p);
        
        color = litGold(p, n, viewDir);
        
        // Add internal glow
        color += vec3(0.8, 0.6, 0.2) * (1.0 - smoothstep(0.0, 0.3, d)) * 0.5;
    }
    
    // Vignette
    float vig = 1.0 - length(vUv - 0.5) * 0.8;
    color *= vig;
    
    gl_FragColor = vec4(color, 1.0);
}