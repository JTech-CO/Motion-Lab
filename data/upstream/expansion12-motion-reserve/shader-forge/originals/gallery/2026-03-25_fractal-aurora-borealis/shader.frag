uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Hash & noise functions
float hash(float n) { return fract(sin(n) * 43758.5453); }
float noise(vec2 x) {
  vec2 i = floor(x);
  vec2 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  float n = i.x + i.y * 57.0;
  return mix(mix(hash(n), hash(n + 1.0), f.x),
             mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y);
}

// Fractal noise using fbm
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

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;
  
  vec2 center = vec2(0.5);
  vec2 dir = uv - center;
  float dist = length(dir);
  float angle = atan(dir.y, dir.x);
  
  float t = uTime * 0.3;
  vec3 color = vec3(0.0);
  
  // Aurora bands with rotation
  float bands = 0.0;
  float baseFreq = 3.0;
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float offset = fi * 0.15;
    float wave = sin(angle * (baseFreq + fi * 0.5) + t * (0.5 + fi * 0.1) + fi * 2.0);
    float noiseVal = fbm(vec2(dist * (2.0 + fi * 0.3) - t * 0.4, fi * 10.0));
    float bandPos = 0.3 + offset + wave * 0.15 + noiseVal * 0.1;
    float glow = exp(-pow((dist - bandPos) * 8.0, 2.0) * 2.0);
    
    // Color palette
    vec3 colA = vec3(0.0, 0.4, 0.1); // Green
    vec3 colB = vec3(0.8, 0.1, 0.4); // Magenta
    vec3 colC = vec3(0.0, 0.1, 0.6); // Blue
    
    float mixVal = fi / 3.0;
    vec3 layerColor;
    if (mixVal < 0.5) layerColor = mix(colA, colB, mixVal * 2.0);
    else layerColor = mix(colB, colC, (mixVal - 0.5) * 2.0);
    
    color += layerColor * glow * 0.7;
  }
  
  // Subtle stars
  float stars = 0.0;
  vec2 starUv = uv * 20.0;
  float starHash = hash(floor(starUv.x) + floor(starUv.y) * 57.0);
  if (starHash > 0.97) stars = 0.8;
  
  // Final composition
  color += vec3(stars);
  color *= 1.0 - smoothstep(0.0, 0.8, dist) * 0.5;
  color = pow(color, vec3(1.2));
  
  gl_FragColor = vec4(color, 1.0);
}