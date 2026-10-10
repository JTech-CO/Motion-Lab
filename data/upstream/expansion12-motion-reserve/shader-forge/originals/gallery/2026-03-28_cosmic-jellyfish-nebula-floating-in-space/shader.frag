uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple hash function for noise
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// 2D noise function
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

// Fractal noise (fbm)
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

// Smooth minimum function
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Signed distance function for a circle
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// Signed distance function for a rounded rectangle
float sdRoundedRect(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b;
    return length(max(q, 0.0)) + r - length(max(q, 0.0));
}

// Signed distance function for a hexagon
float sdHexagon(vec2 p, float r) {
    const vec3 k = vec3(-0.866025, 0.5, 0.57735);
    p = abs(p);
    p -= 2.0 * min(dot(k.xy, p), 0.0) * k.xy;
    return length(p) - r;
}

// Signed distance function for a triangle
float sdTriangle(vec2 p, vec2 p1, vec2 p2, vec2 p3) {
    vec2 a = p2 - p1;
    vec2 b = p3 - p2;
    vec2 c = p1 - p3;
    
    vec2 pa = p - p1;
    vec2 pb = p - p2;
    vec2 pc = p - p3;
    
    float d1 = length(pa - a * clamp(dot(pa, a) / dot(a, a), 0.0, 1.0));
    float d2 = length(pb - b * clamp(dot(pb, b) / dot(b, b), 0.0, 1.0));
    float d3 = length(pc - c * clamp(dot(pc, c) / dot(c, c), 0.0, 1.0));
    
    float w1 = step(d1 * d1, dot(pa, pa) - dot(pa - a, pa - a));
    float w2 = step(d2 * d2, dot(pb, pb) - dot(pb - b, pb - b));
    float w3 = step(d3 * d3, dot(pc, pc) - dot(pc - c, pc - c));
    
    return max(max(d1 * w1, d2 * w2), d3 * w3);
}

void main() {
    // Normalize UV coordinates to -1..1 range with correct aspect ratio
    vec2 uv = (vUv - 0.5) * 2.0;
    uv.x *= uResolution.x / uResolution.y;
    
    // Create a background gradient
    vec3 col = vec3(0.1, 0.1, 0.2) + 0.3 * uv.y;
    
    // Animate the center point
    float time = uTime * 0.5;
    vec2 center = vec2(sin(time * 0.7) * 0.5, cos(time * 0.5) * 0.5);
    
    // Create a dynamic pattern using SDFs
    float d1 = sdCircle(uv - center, 0.3 + 0.1 * sin(time * 2.0));
    float d2 = sdRoundedRect(uv - center * 0.5, vec2(0.2, 0.1), 0.05);
    float d3 = sdHexagon(uv + center * 0.3, 0.25);
    
    // Combine shapes with smooth minimum
    float d = smin(d1, d2, 0.1);
    d = smin(d, d3, 0.1);
    
    // Create a glowing effect based on distance
    float glow = exp(-abs(d) * 5.0);
    
    // Add some noise for texture
    float noiseVal = fbm(uv * 3.0 + time * 0.2);
    glow += noiseVal * 0.1;
    
    // Add color based on distance
    vec3 shapeColor = vec3(0.8, 0.6, 0.9) * glow;
    
    // Add some animated rings
    float ringDist = length(uv - center);
    float ring = sin(ringDist * 10.0 - time * 5.0);
    ring = smoothstep(0.8, 1.0, ring) * 0.3;
    
    // Add some stars
    float stars = hash(uv * 100.0);
    stars = step(0.98, stars) * 0.5;
    
    // Combine all elements
    col += shapeColor + ring + stars;
    
    // Add some color variation based on position
    col += 0.1 * sin(uv.x * 5.0 + time) * vec3(0.5, 0.3, 0.7);
    
    // Apply gamma correction
    col = pow(col, vec3(0.8));
    
    gl_FragColor = vec4(col, 1.0);
}