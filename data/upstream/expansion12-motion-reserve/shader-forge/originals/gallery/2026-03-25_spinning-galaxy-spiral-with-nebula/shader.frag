uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (12.9898 + 78.233 * p.x));
}

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
    vec2 center = vec2(0.5);
    vec2 uvCentered = uv - center;
    
    // Aspect correction
    float aspect = uResolution.x / uResolution.y;
    uvCentered.x *= aspect;
    
    // Rotate UVs
    float angle = uTime * 0.3;
    float c = cos(angle);
    float s = sin(angle);
    mat2 rot = mat2(c, -s, s, c);
    uvCentered *= rot;
    
    // Spiral parameters
    float r = length(uvCentered);
    float a = atan(uvCentered.y, uvCentered.x);
    
    // Logarithmic spiral formula
    float spiral = abs(sin(log(r * 10.0) * 0.8 + a * 0.3 + uTime * 0.5));
    
    // Nebula layers with fbm
    vec2 nebulaUV = uv * 2.0;
    float nebula1 = fbm(nebulaUV + uTime * 0.1);
    float nebula2 = fbm(nebulaUV * 2.0 - uTime * 0.05);
    float nebula3 = fbm(nebulaUV * 4.0 + uTime * 0.02);
    
    // Color palette
    vec3 color1 = vec3(0.1, 0.2, 0.6);   // Deep blue
    vec3 color2 = vec3(0.4, 0.1, 0.7);   // Purple
    vec3 color3 = vec3(0.9, 0.7, 0.2);   // Gold
    
    // Mix colors based on spiral and nebula
    vec3 nebulaColor = mix(color1, color2, nebula1);
    nebulaColor = mix(nebulaColor, color3, nebula2 * 0.3 + nebula3 * 0.2);
    
    // Spiral glow
    float spiralGlow = pow(spiral, 8.0) * 1.5;
    vec3 spiralColor = mix(color2, color3, spiral * 0.5 + 0.5);
    
    // Stars
    float stars = 0.0;
    for (int i = 0; i < 10; i++) {
        float starSize = float(i + 1) / 1000.0;
        float starX = hash(vec2(float(i) * 13.0, 0.0)) * 2.0 - 1.0;
        float starY = hash(vec2(float(i) * 17.0, 1.0)) * 2.0 - 1.0;
        vec2 starPos = vec2(starX, starY);
        
        // Rotate stars
        starPos *= rot;
        
        float dist = length(uvCentered - starPos);
        stars += pow(1.0 - smoothstep(0.0, starSize, dist), 80.0);
    }
    
    // Combine all elements
    vec3 finalColor = nebulaColor * (1.0 - spiral * 0.5) + spiralColor * spiralGlow;
    finalColor += stars * vec3(1.0, 0.9, 0.8);
    
    // Vignette
    float vignette = smoothstep(0.6, 0.9, r * aspect);
    finalColor *= vignette;
    
    // Add some contrast
    finalColor = pow(finalColor, vec3(1.1));
    
    gl_FragColor = vec4(finalColor, 1.0);
}