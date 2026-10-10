#ifdef GL_ES
precision highp float;
#endif

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

vec3 vibrantPalette(float x) {
    // High-contrast palette: vibrant magenta → cyan → electric yellow
    vec3 a = vec3(0.95, 0.1, 0.75);
    vec3 b = vec3(0.1, 0.85, 0.95);
    vec3 c = vec3(1.0, 0.95, 0.1);
    
    // Smooth cycling gradient
    vec3 color;
    if (x < 0.33) {
        color = mix(a, b, x * 3.0);
    } else if (x < 0.66) {
        color = mix(b, c, (x - 0.33) * 3.0);
    } else {
        color = mix(c, a, (x - 0.66) * 3.0);
    }
    
    // Add electric shimmer with subtle phase shift
    float shimmer = 0.15 * sin(x * 6.2831853 + uTime * 2.0);
    color += shimmer;
    
    // Ensure minimum brightness to avoid dark voids
    return clamp(color, 0.12, 1.0);
}

float plasmaField(vec2 uv, float t) {
    // Aspect correction
    float aspect = uResolution.x / uResolution.y;
    uv.x *= aspect;
    
    // Base energy field: superposition of 5 wave functions
    float v1 = sin(uv.x * 1.2 + t * 1.3);
    float v2 = sin(uv.y * 1.1 + t * 0.9);
    float v3 = sin((uv.x + uv.y) * 0.8 + t * 1.1);
    float v4 = sin(length(uv - vec2(aspect * 0.5, 0.5)) * 1.6 + t * 0.7);
    
    // Twisted helical wave for extra complexity
    float v5 = sin(uv.x * 0.4 * sin(t * 0.3) + uv.y * 0.4 * cos(t * 0.4) + t * 0.6);
    
    // Combine with slight non-linear warping
    float plasma = (v1 + v2 + v3 + v4 + v5) / 5.0;
    
    // Add subtle micro-noise for texture
    float noise = hash21(uv * 30.0 + t * 0.2) * 0.1;
    plasma += noise;
    
    // Normalize to 0..1 range
    return clamp(plasma * 0.5 + 0.5, 0.0, 1.0);
}

void main() {
    // Compute UVs in [0,1] range with aspect ratio correction
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    uv.x *= aspect;
    
    // Compute plasma field value
    float val = plasmaField(uv, uTime);
    
    // Map to vibrant color palette
    vec3 color = vibrantPalette(val);
    
    gl_FragColor = vec4(color, 1.0);
}