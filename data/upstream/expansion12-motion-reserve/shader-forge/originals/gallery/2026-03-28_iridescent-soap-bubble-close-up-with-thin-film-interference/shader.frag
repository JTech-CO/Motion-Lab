uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simplex-style 3D noise (based on IQ's value noise)
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float n = i.x + i.y * 57.0 + 113.0 * i.z;
    return mix(mix(mix(hash(vec2(n + 0.0, n + 1.0)), 
                      hash(vec2(n + 2.0, n + 3.0)), f.x),
                   mix(hash(vec2(n + 4.0, n + 5.0)), 
                      hash(vec2(n + 6.0, n + 7.0)), f.x), f.y),
               mix(mix(hash(vec2(n + 8.0, n + 9.0)), 
                      hash(vec2(n + 10.0, n + 11.0)), f.x),
                   mix(hash(vec2(n + 12.0, n + 13.0)), 
                      hash(vec2(n + 14.0, n + 15.0)), f.x), f.y), f.z);
}

float fbm(vec3 p) {
    float f = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        f += a * noise(p);
        p *= 2.02;
        a *= 0.5;
    }
    return f;
}

// Iridescence calculation based on thin-film interference
vec3 getIridescence(vec3 normal, vec3 view, float thickness) {
    float cosTheta = clamp(-dot(view, normal), 0.0, 1.0);
    float phase = (cosTheta + 1.0) * 0.5;
    
    // IOR values for air-soap-water interface
    vec3 ior1 = vec3(1.0);
    vec3 ior2 = vec3(1.33);
    vec3 ior3 = vec3(1.5);
    
    // Film thickness scaled for visible interference
    float t = thickness * 100.0 + 0.1;
    
    // Simplified iridescence model
    vec3 baseColor = vec3(0.9, 0.95, 1.0);
    vec3 ratio = ior2 / ior3;
    float cosThetaSq = cosTheta * cosTheta;
    float term = max(0.0, 1.0 - ratio.x * ratio.x * (1.0 - cosThetaSq));
    vec3 shift = 4.0 * 3.14159 * t * ior2 * sqrt(vec3(term));
    vec3 irid = baseColor * (0.5 + 0.5 * cos(shift + vec3(0.0, 2.0, 4.0)));
    
    return clamp(irid, 0.0, 1.0);
}

// Get film thickness based on surface position (curvature-based)
float getFilmThickness(vec3 p) {
    // Bubble radius
    float r = length(p);
    // Thickness varies with curvature: thinner at poles, thicker at equator
    float thickness = 0.3 + 0.2 * sin(p.y * 3.14159) * cos(p.x * 3.14159);
    // Add subtle variation
    thickness += 0.05 * fbm(p * 2.0);
    return clamp(thickness, 0.05, 0.6);
}

// Raymarch soap bubble
float raymarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 32; i++) {
        vec3 p = ro + rd * t;
        float r = length(p);
        float thickness = getFilmThickness(p);
        
        // SDF for soap bubble: sphere with varying thickness
        float d = abs(r - 1.0) - thickness * 0.3;
        
        if (d < 0.001) return t;
        t += max(0.01, d * 0.5);
        if (t > 10.0) return -1.0;
    }
    return -1.0;
}

// Calculate normal from SDF
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    float d = abs(length(p) - 1.0) - getFilmThickness(p) * 0.3;
    return normalize(vec3(
        abs(length(p + e.xyy) - 1.0) - getFilmThickness(p + e.xyy) * 0.3 - d,
        abs(length(p + e.yxy) - 1.0) - getFilmThickness(p + e.yxy) * 0.3 - d,
        abs(length(p + e.yyx) - 1.0) - getFilmThickness(p + e.yyx) * 0.3 - d
    ));
}

vec3 soapBubble(vec2 uv, float t) {
    // Rotate UV for animation
    float angle = t * 0.3;
    mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
    uv *= rot;
    
    // Camera setup
    vec3 ro = vec3(0.0, 0.0, -2.5);
    vec3 rd = normalize(vec3(uv, 1.0));
    
    // Raymarch bubble
    float d = raymarch(ro, rd);
    
    if (d < 0.0) {
        // Background with subtle gradient
        return vec3(0.05, 0.05, 0.1) + 0.05 * uv.y;
    }
    
    vec3 p = ro + rd * d;
    vec3 normal = calcNormal(p);
    vec3 view = -rd;
    
    // Get iridescence
    float thickness = getFilmThickness(p);
    vec3 irid = getIridescence(normal, view, thickness);
    
    // Fresnel rim lighting
    float fresnel = pow(1.0 - dot(view, normal), 3.0);
    vec3 rim = vec3(0.8, 0.9, 1.0) * fresnel * 0.3;
    
    // Specular highlight
    vec3 lightDir = normalize(vec3(0.5, 0.3, 1.0));
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(reflectDir, view), 0.0), 32.0) * 0.4;
    
    // Combine
    vec3 col = irid + rim + vec3(0.9) * spec;
    
    // Add subtle internal reflection
    vec3 bounce = reflect(view, normal);
    float bounceDist = raymarch(p + bounce * 0.01, bounce);
    if (bounceDist > 0.0) {
        vec3 bounceP = p + bounce * bounceDist;
        col += getIridescence(calcNormal(bounceP), bounce, getFilmThickness(bounceP)) * 0.1;
    }
    
    return clamp(col, 0.01, 1.0);
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 col = soapBubble(uv, uTime);
    
    // Tone mapping and bloom
    col = mix(vec3(0.02), col, 1.2);
    col = pow(clamp(col, 0.0, 1.0), vec3(0.9));
    col += vec3(0.1) * smoothstep(0.8, 1.0, length(uv));
    
    gl_FragColor = vec4(col, 1.0);
}