precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// --- Utilities ---
float hash(vec3 p) {
    p = fract(p * 0.3183099 + .1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0 - 2.0*f);
    return mix(mix(mix(hash(p + vec3(0.0,0.0,0.0)), hash(p + vec3(1.0,0.0,0.0)), f.x),
                   mix(hash(p + vec3(0.0,1.0,0.0)), hash(p + vec3(1.0,1.0,0.0)), f.x), f.y),
               mix(mix(hash(p + vec3(0.0,0.0,1.0)), hash(p + vec3(1.0,0.0,1.0)), f.x),
                   mix(hash(p + vec3(0.0,1.0,1.0)), hash(p + vec3(1.0,1.0,1.0)), f.x), f.y), f.z);
}

float fbm(vec3 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 4; i++) {
        f += w * noise(p);
        w *= 0.5;
        p *= 2.0;
    }
    return f;
}

vec3 rotateY(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}

// --- Iridescence (Thin-film Interference) ---
vec3 iridescence(float thickness, float cosTheta, vec3 base) {
    float phase = thickness * 2.0 + 0.2;
    vec3 shift;
    shift.r = 0.5 + 0.5 * cos(phase - cosTheta * 3.14159);
    shift.g = 0.5 + 0.5 * cos(phase - cosTheta * 3.14159 - 2.0);
    shift.b = 1.0 - shift.r * shift.g;
    return mix(base, vec3(0.6, 0.8, 1.0) * 1.5, shift.r * shift.g * shift.b * 0.8);
}

// --- SDF for Sphere ---
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// --- Tone Mapping ---
vec3 toneMap(vec3 color) {
    return color / (1.0 + color);
}

void main() {
    // Camera setup
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 ro = vec3(0.0, 0.0, -3.0);
    vec3 rd = normalize(vec3(uv, 1.5));
    
    // Sky background
    float sunAngle = uTime * 0.3;
    vec3 sunDir = normalize(vec3(sin(sunAngle), cos(sunAngle * 0.5), cos(sunAngle)));
    float sun = pow(clamp(dot(rd, sunDir), 0.0, 1.0), 16.0);
    vec3 skyColor = vec3(0.7, 0.6, 0.5) + vec3(0.1, 0.05, 0.0) * sun * 2.0;
    skyColor += vec3(0.0, 0.2, 0.4) * (1.0 - rd.y);
    skyColor = clamp(skyColor, 0.0, 1.0);

    // Bubble positions
    vec3 centers[8];
    centers[0] = vec3(0.0, 0.0, 0.0);
    centers[1] = vec3(0.8, 0.2, -0.5);
    centers[2] = vec3(-0.6, -0.4, -0.3);
    centers[3] = vec3(0.2, -0.7, -0.8);
    centers[4] = vec3(-0.5, 0.6, -0.6);
    centers[5] = vec3(0.5, 0.5, -1.2);
    centers[6] = vec3(-0.8, 0.1, -0.9);
    centers[7] = vec3(0.0, 0.8, -0.7);
    
    // Animate bubbles
    for (int i = 0; i < 8; i++) {
        centers[i].x += sin(uTime * 0.7 + float(i)) * 0.2;
        centers[i].y += cos(uTime * 0.5 + float(i * 2)) * 0.15;
        centers[i].z += sin(uTime * 0.3 + float(i * 3)) * 0.1;
    }

    float t = 0.1;
    float maxDist = 10.0;
    vec3 col = skyColor;
    float alpha = 0.0;

    // Raymarch with 128 steps
    for (int i = 0; i < 128; i++) {
        vec3 pos = ro + rd * t;
        float minDist = 1.0;
        
        // Find closest bubble
        for (int j = 0; j < 8; j++) {
            vec3 center = rotateY(centers[j], uTime * 0.2);
            float dist = sdSphere(pos - center, 0.35 + 0.1 * sin(uTime + float(j)));
            minDist = min(minDist, dist);
        }
        
        if (minDist < 0.01) {
            // Surface hit - compute normal
            vec3 eps = vec3(0.001, 0.0, 0.0);
            vec3 normal = normalize(vec3(
                sdSphere(pos + eps.xyy - rotateY(centers[0], uTime * 0.2), 0.35) - 
                sdSphere(pos - eps.xyy - rotateY(centers[0], uTime * 0.2), 0.35),
                sdSphere(pos + eps.yxy - rotateY(centers[0], uTime * 0.2), 0.35) - 
                sdSphere(pos - eps.yxy - rotateY(centers[0], uTime * 0.2), 0.35),
                sdSphere(pos + eps.yyx - rotateY(centers[0], uTime * 0.2), 0.35) - 
                sdSphere(pos - eps.yyx - rotateY(centers[0], uTime * 0.2), 0.35)
            ));
            
            // Fresnel
            float fresnel = pow(1.0 - dot(rd, normal), 5.0);
            
            // Iridescence
            float thickness = 0.08 + 0.02 * fbm(pos * 8.0);
            vec3 baseColor = vec3(0.9, 0.95, 1.0);
            vec3 irid = iridescence(thickness, clamp(dot(rd, normal), 0.0, 1.0), baseColor);
            
            // Specular highlight
            vec3 lightDir = sunDir;
            vec3 reflectDir = reflect(-rd, normal);
            float spec = pow(clamp(dot(reflectDir, lightDir), 0.0, 1.0), 64.0);
            
            // Lighting
            float diff = clamp(dot(normal, lightDir), 0.1, 1.0);
            
            // Combine
            vec3 surfaceColor = irid * diff + vec3(1.0) * spec * 0.5;
            vec3 finalColor = mix(skyColor, surfaceColor, fresnel * 0.8 + 0.2);
            
            // Soft blending
            float density = 0.3;
            float weight = density * 0.08;
            col = mix(col, finalColor, weight * (1.0 - alpha));
            alpha += weight * (1.0 - alpha);
            
            if (alpha > 0.95) break;
        }
        
        t += max(0.02, minDist * 0.5);
        if (t > maxDist) break;
    }

    // Sun glare
    col += vec3(1.0, 0.6, 0.3) * sun * 0.3;
    
    // Tone mapping
    col = toneMap(col);
    
    gl_FragColor = vec4(col, 1.0);
}