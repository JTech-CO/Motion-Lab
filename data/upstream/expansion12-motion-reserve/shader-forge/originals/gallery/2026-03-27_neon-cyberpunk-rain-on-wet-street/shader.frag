uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define PI 3.14159265

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (12.9898 + 78.233));
}

float noise(vec2 p) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    fp = fp * fp * (3.0 - 2.0 * fp);
    float a = hash(ip);
    float b = hash(ip + vec2(1.0, 0.0));
    float c = hash(ip + vec2(0.0, 1.0));
    float d = hash(ip + vec2(1.0, 1.0));
    return mix(mix(a, b, fp.x), mix(c, d, fp.x), fp.y);
}

float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 4; i++) {
        f += w * noise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

void main() {
    vec2 uv = vUv;
    vec2 res = uResolution;
    vec2 ratioUV = (uv - 0.5) * res.xy / min(res.x, res.y);
    
    // Create rain streaks
    float rain = 0.0;
    float speed = 5.0 + uTime * 2.0;
    for (int i = 0; i < 6; i++) {
        float angle = float(i) * 0.5;
        float dx = sin(angle) * 1.0;
        float dy = cos(angle) * 1.0;
        vec2 pos = uv * 10.0 - vec2(dx, dy) * speed;
        float dist = length(pos - uv * 10.0);
        float streak = exp(-dist * dist * 50.0);
        streak *= 0.6 + 0.4 * hash(vec2(float(i), uTime));
        rain += streak;
    }
    
    // Create neon reflections on wet street
    float y = uv.y * 2.0 - 1.0;
    float streetNoise = fbm(vec2(uv.x * 3.0, uv.y * 3.0 + uTime * 0.5));
    float horizon = 0.5 + 0.1 * sin(uv.x * PI + uTime);
    
    // Neon grid on street
    float gridX = sin(uv.x * 8.0) * 0.02;
    float gridY = abs(uv.y - horizon) * 5.0;
    float neonGrid = smoothstep(0.0, 0.02, abs(gridX)) * (1.0 - smoothstep(0.0, 1.0, gridY));
    
    // Neon colors
    vec3 neonBlue = vec3(0.1, 0.5, 1.0);
    vec3 neonPink = vec3(1.0, 0.1, 0.5);
    vec3 neonYellow = vec3(1.0, 1.0, 0.1);
    vec3 groundColor = mix(neonPink, neonBlue, (uv.x + 1.0) * 0.5 + 0.2);
    groundColor = mix(groundColor, neonYellow, neonGrid * 0.3);
    
    // Add rain streaks to neon ground
    vec3 finalColor = mix(groundColor * 0.2, groundColor * 1.2, rain * 0.5);
    
    // Sky gradient
    vec3 skyColor = mix(vec3(0.05, 0.02, 0.1), vec3(0.2, 0.1, 0.4), uv.y);
    finalColor = mix(skyColor, finalColor, smoothstep(0.3, 0.7, uv.y));
    
    // Fog
    float depth = uv.y;
    float fogFactor = exp(-depth * depth * 0.8);
    vec3 fogColor = vec3(0.0, 0.0, 0.05);
    finalColor = mix(fogColor, finalColor, fogFactor);
    
    // Add bright neon highlights
    float glow = pow(rain, 2.0) * 0.8;
    finalColor += neonBlue * glow;
    
    gl_FragColor = vec4(finalColor, 1.0);
}