precision highp float;

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// ──────────────────────── 3D Simplex Noise (Gustavson) ───────────────────────
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}

float fbm(vec3 p) {
  float value = 0.0;
  float amplitude = 0.5;
  float frequency = 1.0;
  for (int i = 0; i < 5; i++) {
    value += amplitude * snoise(p * frequency);
    amplitude *= 0.5;
    frequency *= 2.0;
  }
  return value;
}

// ──────────────────────── Color Functions ───────────────────────
vec3 auroraMix(float t) {
  vec3 green = vec3(0.0, 0.6, 0.15);
  vec3 purple = vec3(0.6, 0.1, 0.8);
  vec3 blue = vec3(0.0, 0.4, 0.9);
  vec3 red = vec3(0.9, 0.1, 0.2);
  
  if (t < 0.25) return mix(green, purple, t * 4.0);
  if (t < 0.5) return mix(purple, blue, (t - 0.25) * 4.0);
  return mix(blue, red, (t - 0.5) * 2.0);
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;
  
  vec2 center = vec2(0.0, 0.5);
  float dist = distance(uv, center);
  
  // Curtain wave parameters
  float t = uTime * 0.15;
  float waveScale = 4.0;
  float curtainHeight = 0.7;
  
  // Create layered curtains with domain warping
  float aurora = 0.0;
  float intensity = 0.0;
  
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    
    // Base wave for each curtain layer
    float base = uv.x * (2.0 + fi * 0.8);
    float wave = sin(base + t + fi * 1.57) * 0.3;
    
    // Noise for organic movement
    float noiseVal = fbm(vec3(uv.x * 3.0 + t * 0.3, fi * 5.0, uv.y * 2.0 + t));
    
    // Vertical position with wave distortion
    float bandCenter = 0.4 + fi * 0.12 + wave * 0.5 + noiseVal * 0.2;
    
    // Gaussian falloff for soft curtains
    float distY = uv.y - bandCenter;
    float curtain = exp(-distY * distY * 25.0) * (0.9 - fi * 0.15);
    
    // Add shimmer effect
    float shimmer = snoise(vec3(uv.x * 10.0 + t * 2.0, fi * 7.0, uv.y * 5.0)) * 0.5 + 0.5;
    curtain *= (0.7 + shimmer * 0.3);
    
    // Layered intensity
    aurora += curtain;
    intensity += curtain * (0.5 + snoise(vec3(uv * 8.0 + t, fi)) * 0.5);
  }
  
  // Global fade at top and bottom
  aurora *= smoothstep(0.0, 0.2, uv.y) * smoothstep(1.0, 0.7, uv.y);
  
  // Color mapping based on aurora intensity and position
  float colorT = aurora * 0.6 + uv.y * 0.4;
  vec3 color = auroraMix(colorT);
  
  // Add purple/magenta highlights at high intensity
  color += vec3(0.8, 0.2, 0.9) * smoothstep(0.6, 1.0, intensity) * 0.3;
  
  // Add subtle green glow
  color += vec3(0.1, 0.7, 0.2) * smoothstep(0.4, 0.8, aurora) * 0.2;
  
  // Vertical gradient for depth
  color *= (0.3 + 0.7 * smoothstep(0.0, 0.8, uv.y));
  
  // Tone mapping
  color = color / (color + 1.0);
  
  gl_FragColor = vec4(color, 1.0);
}