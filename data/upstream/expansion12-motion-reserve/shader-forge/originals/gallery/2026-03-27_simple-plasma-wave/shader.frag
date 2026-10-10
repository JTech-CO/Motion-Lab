uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    uv.x *= aspect;
    
    vec2 p = uv * 3.0;
    float t = uTime * 0.8;
    
    float v1 = sin(p.x + t * 1.3);
    float v2 = sin(p.y * 1.1 + t * 0.9);
    float v3 = sin((p.x + p.y) * 0.8 + t * 1.1);
    float v4 = sin(length(p) * 1.4 + t * 0.6);
    
    float plasma = (v1 + v2 + v3 + v4) * 0.25 + 0.5;
    
    vec3 color;
    if (plasma < 0.33) {
        color = mix(vec3(0.0, 0.0, 1.0), vec3(0.0, 1.0, 0.5), plasma * 3.0);
    } else if (plasma < 0.66) {
        color = mix(vec3(0.0, 1.0, 0.5), vec3(1.0, 0.0, 0.0), (plasma - 0.33) * 3.0);
    } else {
        color = mix(vec3(1.0, 0.0, 0.0), vec3(0.0, 0.0, 1.0), (plasma - 0.66) * 3.0);
    }
    
    float brightness = 0.05 * sin(plasma * 6.2831853 + t * 2.0);
    color += brightness;
    
    gl_FragColor = vec4(color, 1.0);
}