uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Pseudo-random
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453);
}

// 2D noise function
float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

// Fractal Brownian Motion for detailed texture
float fbm(vec2 st) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 0.0;
    for (int i = 0; i < 5; i++) {
        value += amplitude * noise(st);
        st *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// Hash function for 3D noise
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = vUv;
    
    // Adjust aspect ratio
    vec2 uv2 = uv;
    uv2.x *= uResolution.x / uResolution.y;
    
    // Center coordinates
    uv2 = uv2 * 2.0 - 1.0;
    
    // Create time-based rotation
    float time = uTime * 0.2;
    float angle = time;
    float c = cos(angle);
    float s = sin(angle);
    mat2 rot = mat2(c, -s, s, c);
    
    // Apply rotation to UVs
    vec2 p = uv2 * rot;
    
    // Create swirling pattern using FBM
    float d = fbm(p * 3.0 + time * 0.5);
    
    // Add secondary detail layer
    d += 0.3 * fbm(p * 6.0 - time * 0.3);
    
    // Create circular gradient for frame
    float dist = length(uv2);
    d = d * (1.0 - smoothstep(0.8, 1.0, dist));
    
    // Color palette using cosine based colors
    vec3 color1 = vec3(0.2, 0.3, 0.6);
    vec3 color2 = vec3(0.9, 0.6, 0.1);
    vec3 color3 = vec3(0.1, 0.9, 0.8);
    
    vec3 color = mix(color1, color2, smoothstep(-0.2, 0.2, d));
    color = mix(color, color3, smoothstep(0.0, 0.3, d) * (1.0 - dist));
    
    // Add subtle Fresnel-like rim lighting
    float fresnel = pow(1.0 - dot(normalize(vec3(uv2, 0.5)), vec3(0.0, 0.0, 1.0)), 3.0);
    color += vec3(0.1, 0.2, 0.4) * fresnel * 0.8;
    
    // Add subtle noise grain
    float grain = random(uv) * 0.05;
    color += vec3(grain);
    
    // Tone mapping
    color = clamp(color, 0.0, 1.0);
    
    gl_FragColor = vec4(color, 1.0);
}