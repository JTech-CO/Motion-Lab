uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

#define PI 3.14159265
#define MAX_STEPS 64
#define MAX_DIST 100.0
#define SURF_DIST 0.001

// Palette from Winsor & Newton
#define WINDSOR_PURPLE vec3(0.451,0.224,0.596)
#define WINDSOR_TEAL vec3(0.063,0.459,0.655)
#define WINDSOR_GOLD vec3(1.000,0.741,0.000)
#define WINDSOR_BLOOD vec3(0.824,0.231,0.216)
#define WINDSOR_VIOLET vec3(0.220,0.231,0.345)

vec2 rotate(vec2 p, float a) {
    float s = sin(a), c = cos(a);
    return vec2(p.x*c - p.y*s, p.x*s + p.y*c);
}

float hash(float n) { return fract(sin(n)*43758.5453); }

float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0-2.0*f);
    float n = p.x + p.y*57.0 + 113.0*p.z;
    return mix(mix(mix(hash(n+0.0), hash(n+1.0), f.x),
                   mix(hash(n+57.0), hash(n+58.0), f.x), f.y),
               mix(mix(hash(n+113.0), hash(n+114.0), f.x),
                   mix(hash(n+170.0), hash(n+171.0), f.x), f.y), f.z);
}

float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return v;
}

float sdBox(vec3 p, vec3 b) {
    vec3 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, max(d.y, d.z)), 0.0);
}

float sdCylinder(vec3 p, float r, float h) {
    vec2 d = length(p.xz) - r;
    return length(max(vec2(d, p.y), 0.0));
}

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float map(vec3 p) {
    // Stalactites
    vec3 pos = p;
    pos.y += 2.0;
    float d = 1e9;
    
    // Main cave chamber
    float chamber = max(abs(pos.x) - 8.0, max(abs(pos.z) - 6.0, -pos.y + 3.0));
    
    // Stalactites
    for (int i = 0; i < 6; i++) {
        vec3 sp = pos;
        sp.x += sin(float(i)*1.3 + uTime*0.2)*3.0;
        sp.z += cos(float(i)*2.1 + uTime*0.15)*2.0;
        sp.y -= abs(sp.y - 2.0)*0.5;
        float cyl = sdCylinder(sp, 0.3 + 0.5*hash(float(i)*1.7), 4.0);
        d = min(d, cyl);
    }
    
    // Crystalline formations
    vec3 crystalPos = pos;
    crystalPos.x += sin(uTime*0.3)*2.0;
    crystalPos.z += cos(uTime*0.2)*2.0;
    float crystal = sdBox(crystalPos, vec3(0.5, 2.0, 0.5));
    crystal += length(pos.xz)*0.1;
    d = min(d, crystal);
    
    // Bioluminescent mushrooms
    for (int i = 0; i < 5; i++) {
        vec3 mp = pos;
        mp.x += sin(uTime*0.4 + float(i)*1.5)*4.0;
        mp.z += cos(uTime*0.3 + float(i)*2.3)*3.0;
        mp.y = -2.0 + noise(vec3(mp.x*0.3, mp.z*0.3, uTime*0.1))*1.0;
        
        // Mushroom stem
        float stem = sdCylinder(mp - vec3(0.0,1.0,0.0), 0.2, 1.0);
        // Mushroom cap
        float cap = sdSphere(mp - vec3(0.0,1.5,0.0), 0.8 + 0.2*sin(uTime + float(i)));
        d = min(d, min(stem, cap));
    }
    
    return min(d, chamber);
}

float raymarch(vec3 ro, vec3 rd) {
    float d = 0.0;
    for (int i = 0; i < MAX_STEPS; i++) {
        vec3 p = ro + rd*d;
        float dist = map(p);
        d += dist;
        if (dist < SURF_DIST || d > MAX_DIST) break;
    }
    return d;
}

vec3 getNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(map(p + e.xyy) - map(p - e.xyy),
                          map(p + e.yxy) - map(p - e.yxy),
                          map(p + e.yyx) - map(p - e.yyx)));
}

float softshadow(vec3 ro, vec3 rd, float mint, float maxt) {
    float t = mint;
    float res = 1.0;
    for (int i = 0; i < 16; i++) {
        float h = map(ro + rd*t);
        res = min(res, 8.0*h/t);
        t += clamp(h, 0.01, 0.2);
        if (res < 0.01 || t > maxt) break;
    }
    return clamp(res, 0.0, 1.0);
}

vec3 fresnel(vec3 rd, vec3 n, float base) {
    return vec3(base + (1.0 - base) * pow(1.0 - dot(rd, n), 5.0));
}

vec3 sky(vec3 rd) {
    float y = clamp(rd.y, -1.0, 1.0);
    vec3 top = WINDSOR_VIOLET * 0.6 + WINDSOR_PURPLE * 0.4;
    vec3 bottom = WINDSOR_TEAL * 0.7 + vec3(0.1, 0.1, 0.2);
    return mix(bottom, top, pow(1.0 - y, 2.0));
}

void main() {
    vec2 uv = (vUv - 0.5) * vec2(uResolution.x/uResolution.y, 1.0);
    
    // Camera setup
    vec3 ro = vec3(0.0, 2.0, -12.0 + sin(uTime*0.3)*2.0);
    vec3 lookAt = vec3(0.0, 0.0, 0.0);
    vec3 worldUp = vec3(0.0, 1.0, 0.0);
    vec3 forward = normalize(lookAt - ro);
    vec3 right = normalize(cross(forward, worldUp));
    vec3 up = normalize(cross(right, forward));
    vec3 rd = normalize(forward + uv.x*right + uv.y*up);
    
    // Raymarch
    float d = raymarch(ro, rd);
    vec3 color = sky(rd);
    
    if (d < MAX_DIST) {
        vec3 p = ro + rd*d;
        vec3 n = getNormal(p);
        
        // Lighting
        vec3 lightDir = normalize(vec3(0.5, 0.8, -0.5));
        vec3 viewDir = normalize(ro - p);
        
        // Ambient occlusion
        float ao = 1.0 - 0.5*noise(p*3.0);
        
        // Diffuse
        float diff = max(dot(n, lightDir), 0.0);
        
        // Specular
        float spec = pow(max(dot(reflect(-lightDir, n), viewDir), 0.0), 64.0);
        
        // Fresnel
        vec3 fres = fresnel(viewDir, n, 0.2);
        
        // Material colors
        vec3 baseColor = vec3(0.2);
        vec3 crystalColor = mix(WINDSOR_TEAL, WINDSOR_PURPLE, 0.5);
        vec3 mushroomColor = mix(WINDSOR_GOLD, WINDSOR_BLOOD, 0.4);
        
        // Determine surface type
        float noiseVal = noise(p*5.0);
        float isCrystal = step(0.7, noiseVal);
        float isMushroom = step(0.5, noise(p*10.0));
        
        vec3 matColor = mix(vec3(0.1), crystalColor, isCrystal);
        matColor = mix(matColor, mushroomColor, isMushroom);
        
        // Subsurface scattering approximation for mushrooms
        float subsurface = pow(1.0 - max(dot(n, -lightDir), 0.0), 3.0) * isMushroom;
        
        // Light contribution
        float shadow = softshadow(p + n*SURF_DIST*2.0, lightDir, 0.1, 10.0);
        float light = diff * shadow + spec * 0.3;
        
        // Bioluminescent glow
        float glow = (0.5 + 0.5*sin(uTime*2.0 + p.x*3.0)) * isMushroom * 2.0;
        
        // Final color
        color = matColor * (light * ao + 0.2) + vec3(0.3, 0.6, 1.0) * subsurface * 0.8;
        color += vec3(0.8, 0.9, 1.0) * glow;
        color = mix(color, vec3(0.0), 1.0 - exp(-d*0.05)); // Fog
        
        // Refraction simulation for crystals
        color = mix(color, vec3(0.8, 0.9, 1.0), isCrystal*0.3);
        color += fres * 0.5;
    }
    
    // God rays (simple radial gradient)
    float godRays = 1.0 - smoothstep(0.0, 0.8, length(uv - vec2(0.5, 0.3)));
    color += vec3(0.8, 0.6, 0.3) * godRays * 0.3;
    
    // Vignette
    color *= 1.0 - 0.3*length(uv);
    
    gl_FragColor = vec4(color, 1.0);
}