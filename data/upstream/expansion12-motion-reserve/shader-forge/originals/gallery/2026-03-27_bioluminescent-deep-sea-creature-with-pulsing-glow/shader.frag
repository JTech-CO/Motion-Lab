uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Pseudo-random function
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// Simple 2D noise
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
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

// SDF for circle
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// SDF for rounded rectangle
float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b;
    return length(max(q, 0.0)) + r - length(max(q, 0.0));
}

// Soft maximum for smooth blending
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

void main() {
    // Normalize UV to -1..1 with correct aspect ratio
    vec2 uv = (vUv - 0.5) * 2.0;
    uv.x *= uResolution.x / uResolution.y;
    
    // Background color with subtle time-based shift
    vec3 bgColor = vec3(0.05, 0.03, 0.1);
    
    // Create animated fractal background
    float bgNoise = fbm(uv * 2.0 + uTime * 0.1);
    vec3 bg = bgColor + bgNoise * vec3(0.1, 0.2, 0.3);
    
    // Create moving circles
    float sceneSdf = 100.0;
    vec2 closestPoint = vec2(0.0);
    
    // Generate moving particles
    for (int i = 0; i < 3; i++) {
        float timeOffset = uTime * 0.3 + float(i) * 2.0;
        vec2 center = vec2(sin(timeOffset) * 0.5, cos(timeOffset * 0.7) * 0.5);
        float radius = 0.2 + 0.1 * sin(timeOffset * 1.3);
        float sdf = sdCircle(uv - center, radius);
        sceneSdf = smin(sceneSdf, sdf, 0.05);
        
        // Add glow effect for particles
        float glow = exp(-3.0 * abs(sdf));
        bg += glow * vec3(0.8, 0.4, 0.9) * (0.5 + 0.5 * sin(timeOffset * 0.7));
    }
    
    // Add a rotating geometric shape
    float rectSdf = sdRoundRect(uv, vec2(0.3), 0.05);
    sceneSdf = smin(sceneSdf, rectSdf, 0.1);
    
    // Create gradient for the shape edges
    float edge = smoothstep(-0.01, 0.01, -sceneSdf);
    vec3 shapeColor = vec3(0.8, 0.6, 0.4);
    
    // Add Fresnel effect for glow
    float fresnel = pow(1.0 - dot(normalize(vec3(uv, 1.0)), vec3(0.0, 0.0, 1.0)), 3.0);
    
    // Combine background with shape
    vec3 color = mix(bg, shapeColor, edge);
    
    // Add final glow effect
    color += fresnel * vec3(0.3, 0.6, 0.8);
    
    gl_FragColor = vec4(color, 1.0);
}