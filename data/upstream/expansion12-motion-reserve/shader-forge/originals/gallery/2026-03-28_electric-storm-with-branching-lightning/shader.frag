uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(float n) { return fract(sin(n) * 43758.5453123); }

float noise(vec2 x) {
  vec2 i = floor(x);
  vec2 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  float n = i.x + i.y * 57.0;
  return mix(
    mix(hash(n), hash(n + 1.0), f.x),
    mix(hash(n + 57.0), hash(n + 58.0), f.x),
    f.y
  );
}

float fbm(vec2 p, int octaves) {
  float v = 0.0;
  float a = 0.5;
  vec2 shift = vec2(100.0);
  mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
  for (int i = 0; i < 4; ++i) {
    if (i >= octaves) break;
    v += a * noise(p);
    p = rot * p * 2.0 + shift;
    a *= 0.5;
  }
  return v;
}

vec3 lightningBranch(vec2 uv, int idx) {
  vec2 p = uv * 2.0 - 1.0;
  float aspect = uResolution.x / uResolution.y;
  p.x *= aspect;
  
  float t = uTime * 0.8 + float(idx) * 0.7;
  float start = fract(t * 0.3);
  
  vec2 base = p * 3.0 + vec2(0.0, uTime * 0.5);
  vec2 warp = vec2(noise(base.yx + uTime), noise(base.xy - uTime)) * 0.3;
  vec2 pos = base + warp;
  
  float detail = fbm(pos * 4.0, 4);
  float branch = smoothstep(0.4, 0.6, detail) * (1.0 - length(p) * 0.8);
  
  vec3 color = vec3(0.0);
  if (branch > 0.01) {
    float flicker = noise(vec2(uTime * 20.0 + float(idx), detail * 10.0));
    vec3 palette = vec3(0.2, 0.8, 1.0) + 0.5 * sin(uTime + pos.xyx + vec3(0., 2., 4.));
    color = palette * branch * (1.5 + flicker * 0.5);
    color *= exp(-abs(p.y - start * 2.0) * 2.0);
  }
  
  return color;
}

void main() {
  vec2 uv = vUv;
  uv *= uResolution.xy / min(uResolution.x, uResolution.y);
  
  vec3 color = vec3(0.0);
  
  for (int i = 0; i < 3; i++) {
    color += lightningBranch(uv, i);
  }
  
  color = clamp(color, 0.0, 1.0);
  gl_FragColor = vec4(color, 1.0);
}