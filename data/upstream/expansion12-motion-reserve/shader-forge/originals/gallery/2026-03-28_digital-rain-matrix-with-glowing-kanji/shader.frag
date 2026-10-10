uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float kanjiNoise(vec2 p) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    float h = hash(ip + vec2(0.0, 0.0));
    h = mix(h, hash(ip + vec2(1.0, 0.0)), fp.x);
    h = mix(h, hash(ip + vec2(0.0, 1.0)), fp.y);
    h = mix(h, hash(ip + vec2(1.0, 1.0)), fp.x * fp.y);
    return h;
}

vec3 rain(vec2 uv, float t) {
    vec2 uvScaled = uv * vec2(uResolution.x / uResolution.y, 1.0);
    float columnWidth = 12.0;
    float colX = floor(uvScaled.x * columnWidth) / columnWidth;
    float speed = 0.8 + 0.4 * sin(uTime * 0.3);
    float y = uvScaled.y + t * speed;
    
    float trail = kanjiNoise(vec2(colX, y));
    float head = kanjiNoise(vec2(colX, y - 0.1));
    
    float alpha = smoothstep(0.9, 1.0, trail);
    float headAlpha = smoothstep(0.95, 1.0, head);
    
    vec3 baseColor = vec3(0.05, 0.2, 0.05);
    vec3 headColor = vec3(0.9, 1.0, 0.8);
    
    vec3 col = mix(baseColor, headColor, headAlpha);
    col *= alpha;
    
    col += col * 0.2 * (1.0 - alpha);
    
    return col;
}

void main() {
    vec2 uv = vUv;
    vec3 col = vec3(0.0);
    
    col = rain(uv, uTime);
    
    col += pow(col, vec3(2.0)) * 0.3;
    
    gl_FragColor = vec4(col, 1.0);
}