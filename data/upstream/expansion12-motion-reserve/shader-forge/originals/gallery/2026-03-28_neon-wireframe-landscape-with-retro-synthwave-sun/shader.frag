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

float curlNoise(vec2 p) {
    float e = 0.001;
    float n1 = noise(p + vec2(e, 0.0));
    float n2 = noise(p - vec2(e, 0.0));
    float n3 = noise(p + vec2(0.0, e));
    float n4 = noise(p - vec2(0.0, e));
    return (n1 - n2 - n3 + n4) / (2.0 * e);
}

float glow(float d, float strength) {
    return exp(-d * (8.0 / strength));
}

void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    
    float horizon = 0.15;
    float t = uTime * 0.5;
    
    vec3 color = vec3(0.05, 0.0, 0.1);
    
    // Synthwave Sun
    vec2 sunCenter = vec2(0.0, horizon + 0.12);
    float sunDist = length(p - sunCenter);
    float sun = smoothstep(0.12, 0.115, sunDist);
    
    // Sun bands
    float bands = step(0.5, fract((p.y - horizon) * 25.0));
    sun *= mix(1.0, 0.4, bands * step(horizon + 0.02, p.y));
    
    // Sun gradient
    vec3 sunColor = mix(vec3(1.0, 0.9, 0.0), vec3(1.0, 0.2, 0.0), smoothstep(0.0, 0.12, sunDist));
    color += sunColor * sun;
    
    // Sun glow
    float sunGlow = exp(-sunDist * 6.0) * 0.4;
    color += mix(vec3(1.0, 0.5, 0.0), vec3(1.0, 0.0, 1.0), 0.5) * sunGlow;
    
    // Ground grid
    if (p.y < horizon) {
        float depth = 0.3 / max(horizon - p.y, 0.001);
        vec2 gridPos = p * depth;
        
        // Curl noise flow field
        vec2 flow = vec2(curlNoise(gridPos * 0.3 + t * 0.2), curlNoise(gridPos * 0.3 + t * 0.2 + 100.0));
        gridPos += flow * 0.3;
        
        float gridX = gridPos.x + t * 2.0;
        float gridY = gridPos.y + t * 1.5;
        
        float lineX = abs(fract(gridX) - 0.5);
        float lineY = abs(fract(gridY * 0.5) - 0.5);
        
        float sharpness = mix(50.0, 10.0, smoothstep(0.0, 0.3, horizon - p.y));
        float gridLineX = glow(lineX, 0.6);
        float gridLineY = glow(lineY, 0.6);
        
        float distFade = exp((p.y - horizon) * 4.0);
        
        // Accent lines
        float accentX = glow(abs(fract(gridX * 0.25) - 0.5), 0.4) * 0.5;
        float accentY = glow(abs(fract(gridY * 0.125) - 0.5), 0.4) * 0.5;
        
        vec3 gridColor = vec3(0.0, 1.0, 1.0) * (gridLineX + gridLineY) * distFade;
        gridColor += vec3(1.0, 0.0, 1.0) * (accentX + accentY) * distFade * 0.8;
        
        // Color shift over time
        gridColor *= mix(vec3(1.0), vec3(0.3, 0.3, 1.0), sin(t * 0.5) * 0.5 + 0.5);
        
        color += gridColor;
    }
    
    // Horizon glow
    float horizonGlow = exp(-abs(p.y - horizon) * 15.0) * 0.5;
    color += mix(vec3(1.0, 0.0, 1.0), vec3(0.0, 1.0, 1.0), 0.5) * horizonGlow;
    
    // Vignette
    float vignette = 1.0 - dot(uv - 0.5, uv - 0.5) * 2.0;
    color *= clamp(vignette, 0.0, 1.0);
    
    // Tone mapping
    color = min(color, vec3(1.5));
    
    gl_FragColor = vec4(color, 1.0);
}