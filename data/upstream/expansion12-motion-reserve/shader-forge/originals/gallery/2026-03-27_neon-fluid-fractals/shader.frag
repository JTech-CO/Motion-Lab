uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple pseudo-random
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 34.345);
    return fract(p.x * p.y);
}

// Simple 2D noise
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash(i + vec2(0.0, 0.0));
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Fractal noise (fbm)
float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 6; i++) {
        f += w * noise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

// Smooth palette (neon-friendly)
vec3 palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557);
    return a + b * cos(6.28318 * (c * t + d + uTime * 0.1));
}

void main() {
    vec2 uv = vUv;
    vec2 p = (uv - 0.5) * uResolution.x / uResolution.y;
    
    // Rotate coordinate system for fluid motion
    float angle = uTime * 0.2;
    mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
    p *= rot;
    
    // Fluid fractal pattern using fbm
    vec2 q = vec2(0.0);
    float f = 0.0;
    float g = 0.0;
    
    for (int i = 0; i < 4; i++) {
        q = abs(p) - vec2(0.5);
        p = p * 2.0 - vec2(0.5);
        f += fbm(p * 3.0 + uTime * 0.2) * (1.0 / float(i + 1));
        g += fbm(p * 4.0 + vec2(uTime * 0.3, -uTime * 0.2)) * (0.5 / float(i + 1));
    }
    
    // Create fluid-like contours
    float val = f * f + g * 0.7;
    float contour = sin(val * 10.0 - uTime * 2.0) * 0.5 + 0.5;
    
    // Add neon glow based on gradient
    vec2 grad = vec2(
        fbm((p + vec2(0.01, 0.0)) * 3.0) - fbm((p - vec2(0.01, 0.0)) * 3.0),
        fbm((p + vec2(0.0, 0.01)) * 3.0) - fbm((p - vec2(0.0, 0.01)) * 3.0)
    );
    float glow = smoothstep(0.0, 0.3, length(grad));
    
    // Combine palette with fractal
    vec3 color = palette(f + uTime * 0.1);
    
    // Add neon highlights
    vec3 neonColor = vec3(0.8, 0.2, 1.0) * contour * 0.7;
    neonColor += vec3(0.2, 0.9, 0.8) * glow * 0.8;
    
    // Composite
    color += neonColor;
    color *= 0.9 + 0.1 * fbm(vec2(val));
    
    // Soft contrast
    color = pow(color, vec3(1.3));
    
    // Vignette
    float vignette = 1.0 - length(uv - 0.5) * 0.8;
    color *= vignette;
    
    gl_FragColor = vec4(color, 1.0);
}