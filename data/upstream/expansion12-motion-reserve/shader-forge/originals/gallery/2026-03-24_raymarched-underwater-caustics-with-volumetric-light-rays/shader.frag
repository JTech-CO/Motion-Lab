uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 simplex(vec3 p) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024190579445054);
  vec3 i  = floor(p + dot(p, C.yyy));
  vec3 x0 = p - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - C.zzz;
  i = mod(i, 289.0);
  vec4 p4 = vec4(i.x + dot(i.yz, vec2(41.0, 20.0)), i.x + dot(i.yz, vec2(41.0, 20.0)) + 1.0, i.x + dot(i.yz, vec2(41.0, 20.0)) + 2.0, i.x + dot(i.yz, vec2(41.0, 20.0)) + 3.0);
  p4 = fract(p4 * C.w) * 2.0 - 1.0;
  vec3 h = abs(p4.xyz) - 0.5;
  vec3 ox = floor(p4.xyz + h);
  vec3 a0 = p4.xyz - ox;
  p4.xyz = floor(a0 * 2.0) + a0;
  a0 = p4.xyz * C.x;
  vec3 b0 = a0.xxy + a0.yzz * C.y;
  vec3 a1 = a0.xzy + a0.zyx * C.y;
  vec3 a2 = a0.zxy + a0.yzx * C.y;
  vec3 a3 = a0.zzy + a0.yxy * C.y;
  vec4 b1 = b0.xzy + b0.yzx * C.y;
  vec4 b2 = b1.xzy + b1.yzx * C.y;
  vec4 b3 = b1.xzy + b1.yzx * C.y;
  vec4 grad1 = vec4(a0.x, a0.y, a0.z, a0.y) * b0.x + vec4(a0.y, a0.z, a0.x, a0.z) * b0.y + vec4(a0.z, a0.x, a0.y, a0.x) * b0.z;
  vec4 grad2 = vec4(a1.x, a1.y, a1.z, a1.y) * b1.x + vec4(a1.y, a1.z, a1.x, a1.z) * b1.y + vec4(a1.z, a1.x, a1.y, a1.x) * b1.z;
  vec4 grad3 = vec4(a2.x, a2.y, a2.z, a2.y) * b2.x + vec4(a2.y, a2.z, a2.x, a2.z) * b2.y + vec4(a2.z, a2.x, a2.y, a2.x) * b2.z;
  vec4 grad4 = vec4(a3.x, a3.y, a3.z, a3.y) * b3.x + vec4(a3.y, a3.z, a3.x, a3.z) * b3.y + vec4(a3.z, a3.x, a3.y, a3.x) * b3.z;
  vec4 n = grad1 * grad1 + grad2 * grad2 + grad3 * grad3 + grad4 * grad4;
  n = 70.0 - n;
  n = n * n;
  vec4 w = n * n;
  float outX = dot(w, vec4(grad1.x, grad2.x, grad3.x, grad4.x)) * 2.0;
  float outY = dot(w, vec4(grad1.y, grad2.y, grad3.y, grad4.y)) * 2.0;
  float outZ = dot(w, vec4(grad1.z, grad2.z, grad3.z, grad4.z)) * 2.0;
  return vec3(outX, outY, outZ);
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;
  
  // Fish-eye distortion at edges
  vec2 uvCentered = uv - 0.5;
  float r = length(uvCentered);
  uv += uvCentered * r * r * 0.15;
  
  float t = uTime * 0.5;
  vec3 color = vec3(0.02, 0.05, 0.1);
  
  // Volumetric rays (god rays)
  vec2 rayUV = uv;
  rayUV.y *= aspect;
  float rayDensity = 0.0;
  for (int i = 0; i < 4; i++) {
    float angle = float(i) * 1.57 + t * 0.3 + float(i) * 0.7;
    vec2 dir = vec2(cos(angle), sin(angle));
    float dist = abs(dot(rayUV - 0.5, dir));
    rayDensity += smoothstep(0.8, 0.0, dist) * 0.04;
  }
  
  // Water surface noise
  float wave = 0.0;
  wave += sin(uv.x * 5.0 + t) * 0.1;
  wave += sin(uv.x * 8.0 - t * 0.7) * 0.08;
  wave += noise(uv * 3.0 + t * 0.2) * 0.05;
  
  // Simplex noise for 3D caustic structure
  vec3 p = vec3(uv * 4.0, t * 0.3);
  p.y += wave * 2.0;
  vec3 n = simplex(p * 2.0);
  
  // Caustic pattern from refracted light
  float caustic = 0.0;
  caustic += pow(1.0 - smoothstep(0.0, 0.5, length(n.xy)), 2.0) * 0.8;
  caustic += pow(1.0 - smoothstep(0.0, 0.3, length(n.yz)), 2.0) * 0.5;
  caustic += noise(uv * 6.0 + t * 0.4) * 0.1;
  
  // Deep blue-teal base
  vec3 deepColor = vec3(0.0, 0.1, 0.3);
  vec3 lightColor = vec3(0.8, 0.95, 1.0);
  
  // Add volumetric rays
  color += lightColor * rayDensity;
  
  // Add caustics as bright highlights
  color += lightColor * caustic;
  
  // Add subtle surface shimmer
  float shimmer = noise(uv * 10.0 + t * 2.0) * 0.05;
  color += vec3(0.1, 0.2, 0.3) * shimmer;
  
  // Vignette
  float vig = 1.0 - length(uv - 0.5) * 0.4;
  color *= vig;
  
  // Tone mapping
  color = color / (color + 1.0);
  
  gl_FragColor = vec4(color, 1.0);
}