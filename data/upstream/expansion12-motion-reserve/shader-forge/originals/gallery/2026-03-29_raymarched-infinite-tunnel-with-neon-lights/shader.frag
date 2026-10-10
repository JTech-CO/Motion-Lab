uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

vec3 hash33(vec3 p) {
    float n = sin(dot(p, vec3(7, 157, 113)));
    return fract(vec3(2097152, 262144, 32768) * n);
}

float sdTunnel(vec3 p) {
    p.z += uTime * 2.0;
    float r = 1.5 + 0.3 * sin(p.z * 0.5 + p.x * 0.2);
    vec3 h = hash33(floor(p * 0.5));
    p.xy += h.xy * 0.5 * sin(p.z * 0.3);
    return length(p.xy) - r;
}

vec3 getNeonColor(vec3 p, float t) {
    vec3 c1 = vec3(1.0, 0.2, 0.8);
    vec3 c2 = vec3(0.2, 0.9, 1.0);
    float f = fract(sin(dot(p.xy, vec2(12.9898, 78.233))) * 43758.5453);
    return mix(c1, c2, 0.5 + 0.5 * sin(uTime + p.z * 2.0 + f * 6.28));
}

void main() {
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    vec3 ro = vec3(0.0, 0.0, uTime * 2.0);
    vec3 rd = normalize(vec3(uv, 1.0));
    
    float t = 0.0;
    vec3 col = vec3(0.0);
    
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float dist = sdTunnel(p);
        
        if (dist < 0.001) {
            vec3 n = normalize(vec3(
                sdTunnel(p + vec3(0.001, 0.0, 0.0)) - dist,
                sdTunnel(p + vec3(0.0, 0.001, 0.0)) - dist,
                sdTunnel(p + vec3(0.0, 0.0, 0.001)) - dist
            ));
            
            vec3 lightDir = normalize(vec3(0.0, 0.0, 1.0));
            float diff = max(dot(n, lightDir), 0.0);
            float spec = pow(max(dot(reflect(-lightDir, n), -rd), 0.0), 32.0);
            
            vec3 neon = getNeonColor(p, t);
            vec3 ambient = neon * 0.3;
            vec3 diffuse = neon * diff * 0.7;
            vec3 specular = vec3(1.0) * spec * 0.5;
            
            col = ambient + diffuse + specular;
            break;
        }
        
        t += dist;
        if (t > 50.0) break;
    }
    
    col = clamp(col, 0.0, 1.0);
    col = pow(col, vec3(0.4545));
    gl_FragColor = vec4(col, 1.0);
}