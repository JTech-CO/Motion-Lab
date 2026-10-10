uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    return fract(p.x * p.y * (p.x + p.y));
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
    float v = 0.0;
    float a = 0.5;
    vec2 shift = vec2(100.0);
    mat2 rot = mat2(cos(0.5), -sin(0.5), sin(0.5), cos(0.5));
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = rot * p * 2.0 + shift;
        a *= 0.5;
    }
    return v;
}

vec3 palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557);
    return a + b * cos(6.28318 * (c * t + d));
}

void main() {
    vec2 uv = vUv;
    uv.x *= uResolution.x / uResolution.y;
    
    // Sky
    float y = uv.y;
    vec3 sky = mix(vec3(0.05, 0.02, 0.1), vec3(0.0), y);
    sky = mix(sky, vec3(0.2, 0.0, 0.3), smoothstep(0.3, 0.7, uv.y));
    sky += vec3(0.1, 0.05, 0.15) * pow(1.0 - uv.y, 8.0);
    
    // Sun
    vec2 sunPos = vec2(0.0, 0.3);
    float sunDist = length(uv - sunPos);
    vec3 sunColor = vec3(0.9, 0.5, 0.1);
    float sun = smoothstep(0.2, 0.0, sunDist) * sunColor.r;
    sun += smoothstep(0.3, 0.1, sunDist) * sunColor.g;
    sun += smoothstep(0.2, 0.0, sunDist) * sunColor.b;
    sky += sun * 0.8;
    
    // Sun rays
    float angle = atan(uv.y - sunPos.y, uv.x - sunPos.x);
    float rays = smoothstep(0.0, 0.02, abs(sin(angle * 10.0 + uTime * 2.0))) * 0.2;
    rays *= smoothstep(0.0, 0.6, sunDist);
    sky += rays;
    
    // Horizon grid
    float gridY = uv.y * 2.0 - 1.0;
    float gridX = uv.x * 2.0 - 1.0;
    float grid = 0.0;
    
    // Perspective grid effect
    float z = 1.0 / (gridY + 0.1);
    vec2 gridUV = vec2(gridX * z, gridY);
    
    float timeOffset = uTime * 0.5;
    float vGrid = mod(gridUV.y + timeOffset, 0.1) - 0.05;
    float hGrid = mod(gridUV.x + timeOffset * 2.0, 0.2) - 0.1;
    
    vGrid = smoothstep(0.0, 0.02, abs(vGrid));
    hGrid = smoothstep(0.0, 0.02, abs(hGrid));
    grid = vGrid + hGrid;
    
    // Grid color with perspective falloff
    float gridAlpha = smoothstep(0.0, 0.3, gridY) * smoothstep(1.0, 0.0, gridY);
    vec3 gridColor = vec3(0.9, 0.2, 0.8);
    vec3 gridLine = gridColor * grid * gridAlpha * 2.0;
    
    // Mountains
    float mountains = fbm(uv * 3.0 + uTime * 0.1);
    mountains = smoothstep(0.3, 0.0, mountains);
    vec3 mountainColor = palette(uv.y + uv.x * 0.5 + uTime * 0.1);
    mountainColor = mix(vec3(0.2, 0.1, 0.3), mountainColor, mountains);
    
    // Combine layers
    vec3 color = sky;
    color = mix(color, mountainColor * 0.8, smoothstep(0.3, 0.0, uv.y));
    color += gridLine;
    
    // Stars
    float stars = hash(uv * 100.0) > 0.97 ? 1.0 : 0.0;
    color += vec3(1.0) * stars * 0.5;
    
    gl_FragColor = vec4(color, 1.0);
}