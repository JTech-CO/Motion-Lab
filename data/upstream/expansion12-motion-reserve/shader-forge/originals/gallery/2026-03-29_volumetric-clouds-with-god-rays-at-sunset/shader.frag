uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash12(vec2 p) {
    float n = sin(dot(p, vec2(159.7334673, 381.2015801))) * 159.7334673;
    return fract(n);
}

vec2 hash22(vec2 p) {
    float n1 = sin(dot(p, vec2(159.7334673, 381.2015801))) * 159.7334673;
    float n2 = sin(dot(p, vec2(251.7334673, 481.2015801))) * 251.7334673;
    return fract(vec2(n1, n2));
}

float worleyNoise(vec2 uv, float freq) {
    uv *= freq;
    vec2 id = floor(uv);
    vec2 gv = fract(uv);
    float minDist = 100.0;
    for (float y = -1.0; y <= 1.0; ++y) {
        for (float x = -1.0; x <= 1.0; ++x) {
            vec2 offset = vec2(x, y);
            vec2 h = hash22(id + offset) * 0.8 + 0.1;
            h += offset;
            vec2 d = gv - h;
            minDist = min(minDist, dot(d, d));
        }
    }
    return minDist;
}

float cloudShape(vec3 p) {
    float t = uTime * 0.15;
    vec2 uv = p.xz * 0.002;
    uv.x += t;
    
    float base = 1.0 - worleyNoise(uv, 1.6);
    float detail = 1.0 - worleyNoise(uv * 4.0, 8.0);
    
    float fbm = base * 0.625 + (base * 0.25 + detail * 0.125);
    return smoothstep(0.4, 0.7, fbm);
}

float densityAt(vec3 p) {
    float h = p.y * 0.001;
    float coverage = smoothstep(0.0, 1.0, h);
    float shape = cloudShape(p);
    return clamp(shape * coverage * 0.3, 0.0, 1.0);
}

vec3 renderClouds(vec2 uv, vec3 rd, vec3 sunDir) {
    vec3 ro = vec3(0.0, 0.0, -1.5);
    float t = 0.0;
    float dist = 3.0;
    float stepSize = dist / 32.0;
    float totalDensity = 0.0;
    
    for (int i = 0; i < 32; i++) {
        vec3 pos = ro + rd * t;
        float d = densityAt(pos);
        totalDensity += d * stepSize;
        t += stepSize;
    }
    
    float extinction = exp(-totalDensity * 1.5);
    vec3 cloudColor = vec3(1.0, 0.95, 0.9) * (1.0 - extinction);
    
    return cloudColor;
}

vec3 godRays(vec2 uv, vec3 sunDir) {
    vec3 ro = vec3(0.0, 0.0, -1.5);
    float marchDist = 2.0;
    float steps = 16.0;
    vec2 sunDir2D = normalize(sunDir.xz) * marchDist / steps;
    vec2 marchUv = uv;
    float lightAccum = 1.0;
    
    for (float i = 0.0; i < steps; i++) {
        marchUv += sunDir2D;
        float d = cloudShape(vec3(marchUv.x * 500.0, 0.0, marchUv.y * 500.0));
        lightAccum *= clamp(1.0 - d * 0.8, 0.0, 1.0);
    }
    
    float sunDot = clamp(dot(normalize(vec3(uv, 0.0)), sunDir), 0.0, 1.0);
    float sun = 0.005 / pow(length(uv - sunDir.xz * 0.5), 1.7);
    
    return vec3(lightAccum * sun * 3.0 * pow(sunDot, 8.0));
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 sunDir = normalize(vec3(cos(uTime * 0.15), sin(uTime * 0.15), 0.5));
    
    vec3 rd = normalize(vec3(uv, 1.5));
    
    vec3 skyColor = mix(vec3(0.1, 0.05, 0.0), vec3(0.9, 0.4, 0.1), smoothstep(-1.0, 1.0, uv.y));
    vec3 clouds = renderClouds(uv, rd, sunDir);
    vec3 godRaysCol = godRays(uv, sunDir);
    
    vec3 color = skyColor + clouds + godRaysCol;
    color = clamp(color, 0.0, 1.0);
    
    gl_FragColor = vec4(color, 1.0);
}