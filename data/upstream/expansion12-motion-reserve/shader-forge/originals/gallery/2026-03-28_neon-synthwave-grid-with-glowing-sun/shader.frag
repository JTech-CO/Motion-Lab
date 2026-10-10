uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple pseudo-random noise
float hash(vec2 p) {
    float a = dot(p, vec2(127.1, 311.7));
    return fract(sin(a) * 43758.5453);
}

// Value noise
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// HSV to RGB conversion for neon palette
const vec4 hsv2rgb_K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
vec3 hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.xxx + hsv2rgb_K.xyz) * 6.0 - hsv2rgb_K.www);
    return c.z * mix(hsv2rgb_K.xxx, clamp(p - hsv2rgb_K.xxx, 0.0, 1.0), c.y);
}

// Glow falloff function
float glow(float d, float strength) {
    return exp(-d * (8.0 / strength));
}

void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    
    // Center UVs and correct aspect
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    
    // Horizon line for synthwave perspective
    float horizon = 0.2;
    float groundY = horizon - p.y;
    
    vec3 color = vec3(0.02, 0.01, 0.05); // Dark sky background
    
    // Time-based parameters
    float t = uTime * 0.3;
    
    // === SKY SECTION ===
    // Sun position
    vec2 sunCenter = vec2(0.0, horizon + 0.15);
    float sunDist = length(p - sunCenter);
    
    // Sun glow
    float sunGlow = glow(sunDist, 0.8);
    vec3 sunColor = hsv2rgb(vec3(0.05 + 0.05 * sin(uTime * 0.5), 1.0, 1.0));
    color += sunColor * sunGlow * 1.5;
    
    // Sun bands (horizontal stripes)
    float bands = step(0.5, fract(p.y * 25.0 + t));
    color += sunColor * 0.3 * bands * step(horizon + 0.05, p.y);
    
    // Sky gradient
    float skyFade = smoothstep(horizon + 0.3, horizon - 0.2, p.y);
    vec3 skyColor = hsv2rgb(vec3(0.6 + 0.1 * sin(uTime * 0.3), 0.8, 0.3 + 0.2 * skyFade));
    color += skyColor * (1.0 - skyFade) * 0.5;
    
    // === GROUND GRID SECTION ===
    if (p.y < horizon) {
        // Perspective projection
        float depth = 0.3 / max(groundY, 0.001);
        
        // Grid coordinates with scrolling
        float gridX = p.x * depth + t;
        float gridY = depth + t * 0.5;
        
        // Grid line distances
        float lineX = abs(fract(gridX) - 0.5);
        float lineY = abs(fract(gridY * 0.5) - 0.5);
        
        // Sharpness based on distance
        float sharpness = mix(50.0, 10.0, smoothstep(0.0, 0.3, groundY));
        
        // Main grid lines
        float gridLineX = glow(lineX, 0.6);
        float gridLineY = glow(lineY, 0.6);
        
        // Distance fade
        float distFade = exp(-groundY * 4.0);
        
        // Neon cyan main lines
        vec3 gridColor = vec3(0.0, 1.0, 1.0) * (gridLineX + gridLineY) * distFade;
        
        // Magenta accent lines (every 4th)
        float accentX = glow(abs(fract(gridX * 0.25) - 0.5), 0.4) * 0.5;
        float accentY = glow(abs(fract(gridY * 0.125) - 0.5), 0.4) * 0.5;
        gridColor += vec3(1.0, 0.0, 1.0) * (accentX + accentY) * distFade;
        
        // Horizon glow
        float horizonGlow = exp(-abs(p.y - horizon) * 15.0) * 0.8;
        gridColor += vec3(1.0, 0.3, 0.8) * horizonGlow;
        
        color += gridColor;
    }
    
    // Vignette
    float vignette = 1.0 - dot(uv - 0.5, uv - 0.5) * 2.0;
    vignette = clamp(vignette, 0.0, 1.0);
    color *= vignette;
    
    // Final tone mapping
    color = min(color, vec3(1.5));
    
    gl_FragColor = vec4(color, 1.0);
}