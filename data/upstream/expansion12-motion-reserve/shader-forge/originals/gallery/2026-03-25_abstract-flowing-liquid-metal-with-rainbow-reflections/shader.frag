uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

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

void main() {
    vec2 uv = vUv;
    vec2 p = uv * 2.0 - 1.0;
    p.x *= uResolution.x / uResolution.y;
    
    float t = uTime * 0.5;
    
    // Create animated organic patterns
    float d = fbm(p * 3.0 + t);
    float e = fbm(p * 5.0 - t * 0.7);
    float f = fbm(p * 8.0 + t * 0.3);
    
    // Combine layers for interesting structure
    float shape = sin(d * 3.14159) * 0.5 + 0.5;
    shape += sin(e * 3.14159 + 1.0) * 0.25;
    shape += cos(f * 3.14159) * 0.25;
    
    // Add some radial distortion
    float dist = length(p);
    shape += sin(dist * 10.0 - t * 2.0) * 0.1;
    
    // Color palette
    vec3 color1 = vec3(0.1, 0.2, 0.4);
    vec3 color2 = vec3(0.8, 0.3, 0.6);
    vec3 color3 = vec3(0.2, 0.7, 0.9);
    
    // Create gradients
    vec3 color = mix(color1, color2, shape);
    color = mix(color, color3, sin(d * 3.14159) * 0.5 + 0.5);
    
    // Add lighting effect
    float fresnel = pow(1.0 - dot(normalize(vec3(p, 1.0)), vec3(0.0, 0.0, 1.0)), 3.0);
    color += vec3(0.5, 0.8, 1.0) * fresnel * 0.3;
    
    // Add subtle noise for texture
    color += vec3(noise(uv * 20.0)) * 0.05;
    
    gl_FragColor = vec4(color, 1.0);
}