precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simplex noise implementation (adapted for WebGL)
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec2 v) {
    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy) );
    vec2 x0 = v -   i + dot(i, C.xx);
    vec2 i1;
    i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod289(i);
    vec4 p = permute(permute(i.y + vec4(0.0, float(i1.y), 1.0, 1.0 + float(i1.y))) + i.x + vec4(0.0, float(i1.x), 1.0, 1.0 + float(i1.x)));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
    m = m*m ;
    m = m*m ;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
    vec3 g;
    g.x  = a0.x  * x0.x  + h.x  * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
}

float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 5; i++) {
        f += w * snoise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec2 rotate(vec2 p, float a) {
    float s = sin(a);
    float c = cos(a);
    return vec2(p.x * c - p.y * s, p.x * s + p.y * c);
}

void main() {
    vec2 uv = vUv;
    uv = uv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec2 p = uv;
    float time = uTime * 0.8;
    
    // Center of the ball
    vec2 center = vec2(0.0);
    float dist = length(p);
    
    // Base sphere color using sine-based plasma
    float plasma = 0.0;
    plasma += sin(p.x * 3.0 + time * 1.5);
    plasma += sin(p.y * 3.0 - time * 1.2);
    plasma += sin((p.x + p.y) * 2.0 + time * 0.8);
    plasma += sin(length(p) * 4.0 - time * 2.0);
    
    // FBM noise for tendrils
    float noiseVal = fbm(p * 3.0 + vec2(time * 0.2));
    float tendrils = fbm(p * 6.0 + vec2(time * 0.8));
    
    // Electric arcs using hash and noise
    float arc = 0.0;
    float arcTime = time * 2.0;
    for (int i = 0; i < 3; i++) {
        float angle = float(i) * 2.094 + arcTime * 0.3;
        vec2 arcDir = vec2(cos(angle), sin(angle));
        float d = abs(p.x * arcDir.y - p.y * arcDir.x);
        float intensity = exp(-d * d * 50.0);
        arc += intensity * (0.5 + 0.5 * snoise(p * 10.0 + arcTime * 2.0));
    }
    
    // Combine effects
    float energy = plasma * 0.2 + tendrils * 0.4 + arc * 0.6;
    
    // Create glowing core
    float core = exp(-dist * dist * 8.0);
    
    // Color palette: cyan-magenta-yellow
    vec3 color1 = vec3(0.0, 0.9, 1.0);   // Cyan
    vec3 color2 = vec3(1.0, 0.0, 0.8);   // Magenta
    vec3 color3 = vec3(1.0, 1.0, 0.0);   // Yellow
    
    // Interpolate colors based on plasma value
    vec3 baseColor = mix(color1, color2, 0.5 + 0.5 * sin(energy * 3.14159));
    baseColor = mix(baseColor, color3, 0.3 + 0.3 * cos(energy * 2.0));
    
    // Add pulsating effect
    float pulse = 0.8 + 0.2 * sin(time * 3.0);
    baseColor *= pulse;
    
    // Combine core and tendrils
    float total = core * 0.7 + energy * 0.6;
    total = clamp(total, 0.0, 1.0);
    
    vec3 finalColor = baseColor * total;
    
    // Bloom glow effect: add high-frequency highlights
    finalColor += vec3(0.5) * arc * 0.5;
    
    // Add white center for intense core
    finalColor += vec3(1.0) * core * 0.3;
    
    gl_FragColor = vec4(finalColor, 1.0);
}