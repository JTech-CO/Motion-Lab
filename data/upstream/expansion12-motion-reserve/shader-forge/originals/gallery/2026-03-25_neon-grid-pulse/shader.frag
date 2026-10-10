uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Hash & noise
float hash(vec2 p) {
    float n = sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123;
    return fract(n);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float n = i.x + i.y * 57.0;
    return mix(mix(hash(vec2(n)), hash(vec2(n + 1.0)), f.x),
               mix(hash(vec2(n + 57.0)), hash(vec2(n + 58.0)), f.x), f.y);
}

// Glow function
float glow(float d, float s) { return exp(-d * d * s); }

void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    
    float t = uTime * 0.8;
    
    // Grid parameters
    float zoom = 1.2 + sin(t * 0.3) * 0.4;
    vec2 gridUV = p * zoom;
    
    // Moving grid
    float speed = 1.5;
    float gridX = gridUV.x + t * speed * 0.3;
    float gridY = gridUV.y + t * speed * 0.3;
    
    // Base grid lines
    float lineX = abs(fract(gridX) - 0.5);
    float lineY = abs(fract(gridY) - 0.5);
    
    // Perspective effect
    float depth = 1.0 + length(p) * 0.5;
    float sharpness = 60.0 / depth;
    
    // Main grid glow
    float gridXGlow = glow(lineX * 20.0, sharpness);
    float gridYGlow = glow(lineY * 20.0, sharpness);
    
    // Accent lines every 4th
    float accentX = glow(abs(fract(gridX * 0.25) - 0.5) * 20.0, sharpness) * 0.5;
    float accentY = glow(abs(fract(gridY * 0.25) - 0.5) * 20.0, sharpness) * 0.5;
    
    // Color palette
    vec3 baseColor = vec3(0.0, 0.8, 1.0);     // Cyan
    vec3 accentColor = vec3(1.0, 0.0, 1.0);   // Magenta
    
    // Combine grid
    float grid = (gridXGlow + gridYGlow);
    grid += accentX + accentY;
    
    // Pulsing effect
    float pulse = 0.7 + 0.3 * sin(t * 2.0);
    grid *= pulse;
    
    // Perspective falloff
    grid *= exp(-abs(p.y) * 0.8);
    
    // Background noise
    vec3 bg = vec3(0.03);
    bg += vec3(0.05) * noise(p * 2.0 + t * 0.1);
    
    // Center glow
    float centerGlow = glow(length(p) * 0.8, 20.0);
    vec3 centerColor = vec3(0.2, 0.6, 1.0) * centerGlow;
    
    // Combine colors
    vec3 color = bg;
    color += baseColor * grid * 0.8;
    color += accentColor * (accentX + accentY) * 0.6;
    color += centerColor;
    
    // Vignette
    float vignette = 1.0 - dot(uv - 0.5, uv - 0.5) * 1.5;
    color *= clamp(vignette, 0.0, 1.0);
    
    // Tone mapping
    color = color / (color + 1.0);
    
    gl_FragColor = vec4(color, 1.0);
}