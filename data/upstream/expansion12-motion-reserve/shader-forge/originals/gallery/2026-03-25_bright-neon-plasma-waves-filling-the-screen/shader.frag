uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define PI 3.14159265359
#define TAU 6.28318530718

// Simple pseudo-random hash
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (1.0 + uTime * 0.2));
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

// FBM noise
float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 5; i++) {
        f += w * noise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

// Palette function for neon colors
vec3 palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557); // Cyan-ish
    vec3 e = vec3(0.651, 0.231, 0.231); // Magenta-ish
    vec3 f = vec3(0.592, 0.690, 0.137); // Yellow-ish
    
    return a + b * cos(TAU * (c * t + d));
}

void main() {
    vec2 uv = vUv;
    
    // Fix aspect ratio
    uv = (uv - 0.5) * vec2(uResolution.x / uResolution.y, 1.0) + 0.5;
    
    // Base coordinates
    vec2 p = uv * 3.0;
    
    // Create plasma using layered FBM with rotation
    float t = uTime * 0.4;
    
    // Layer 1: Rotated waves
    float x = p.x * cos(t * 0.5) - p.y * sin(t * 0.5);
    float y = p.x * sin(t * 0.5) + p.y * cos(t * 0.5);
    float f = fbm(vec2(x * 1.5, y * 1.5));
    
    // Layer 2: Diagonal movement
    f += 0.5 * fbm(vec2(p.x + t * 0.3, p.y - t * 0.2));
    
    // Layer 3: Circular waves
    float r = length(p - 0.5);
    f += 0.5 * sin(r * 6.0 - t * 2.0);
    
    // Layer 4: Interference pattern
    vec2 q = vec2(cos(p.y * 2.0 + t), sin(p.x * 2.0 - t));
    f += 0.25 * fbm(p + 0.5 * q);
    
    // Normalize to 0-1
    f = f / 2.25;
    
    // Apply neon palette with vibrant color shifting
    vec3 color = palette(f * 1.5 + t * 0.2);
    
    // Boost contrast for neon effect
    color = pow(color, vec3(1.8));
    
    // Add bright highlights
    float bright = smoothstep(0.6, 0.9, f);
    color += bright * vec3(0.3, 0.3, 0.5);
    
    // Add glow around high values
    float glow = pow(f, 3.0);
    color += glow * vec3(0.8, 0.4, 1.0);
    
    // Ensure vibrant colors
    color = clamp(color, 0.0, 1.0);
    
    gl_FragColor = vec4(color, 1.0);
}