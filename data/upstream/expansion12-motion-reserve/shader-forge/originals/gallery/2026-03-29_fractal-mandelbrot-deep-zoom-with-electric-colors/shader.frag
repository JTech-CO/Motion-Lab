uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

float mandelbrot(vec2 c) {
    vec2 z = vec2(0.0);
    float iter = 0.0;
    const float B = 4.0;
    const float maxIter = 100.0;
    
    for (int i = 0; i < 100; i++) {
        if (i >= int(maxIter)) break;
        z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + c;
        if (dot(z, z) > B) break;
        iter += 1.0;
    }
    
    if (iter >= maxIter) return 0.0;
    
    float sn = iter - log2(log2(dot(z, z))) + 4.0;
    return sn;
}

vec3 getPalette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557);
    
    return a + b * cos(6.28318 * (c * t + d + uTime * 0.1));
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    float zoom = 0.6 + 0.4 * sin(uTime * 0.2);
    vec2 offset = vec2(sin(uTime * 0.15) * 0.7, cos(uTime * 0.1) * 0.5);
    
    vec2 c = uv * zoom + offset;
    float iter = mandelbrot(c);
    
    vec3 color = vec3(0.0);
    if (iter > 0.0) {
        float t = iter * 0.08;
        color = getPalette(t);
        
        float glow = pow(smoothstep(0.0, 1.0, iter * 0.1), 3.0);
        color += vec3(0.8, 0.4, 1.0) * glow * 0.6;
        
        color *= 1.2;
        color = clamp(color, 0.0, 1.0);
    }
    
    gl_FragColor = vec4(color, 1.0);
}