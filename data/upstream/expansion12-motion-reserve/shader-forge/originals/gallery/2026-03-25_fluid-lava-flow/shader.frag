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

vec3 palette(float t) {
  vec3 a = vec3(0.8, 0.3, 0.1);
  vec3 b = vec3(0.6, 0.1, 0.0);
  vec3 c = vec3(1.0, 0.9, 0.7);
  vec3 d = vec3(0.0, 0.0, 0.0);
  return a + b * cos(6.28318 * (c * t + d));
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;
  uv = uv * 2.0 - 1.0;

  float t = uTime * 0.6;
  vec3 color = vec3(0.0);

  // Base flow
  float flow = 0.0;
  float scale = 1.0;
  
  // Layered noise for lava texture
  for (int i = 0; i < 5; i++) {
    float f = pow(2.0, float(i));
    float amp = pow(0.5, float(i));
    
    vec2 p = uv * scale / f + t * vec2(0.3, 0.7);
    flow += (noise(p) * 2.0 - 1.0) * amp;
    flow += (noise(p + vec2(2.3, 5.7)) * 2.0 - 1.0) * amp * 0.5;
    
    scale *= 1.5;
  }

  // Temperature-based color mapping
  float temp = smoothstep(-0.3, 0.8, flow);
  color = mix(palette(0.65), palette(0.95), temp);
  color = mix(color, palette(0.2), smoothstep(0.0, 0.4, flow));

  // Add hot core highlights
  float hot = smoothstep(0.6, 0.95, flow);
  hot = pow(hot, 3.0);
  color += vec3(1.0, 0.3, 0.1) * hot * 0.8;

  // Smooth edges with gradient
  float edge = smoothstep(-0.4, 0.4, flow);
  color *= edge * 0.7 + 0.3;

  // Add movement swirls
  float swirl = length(uv) * 0.5;
  float swirlTime = t * 0.3 + swirl * 2.0;
  vec2 swirlOffset = vec2(cos(swirlTime), sin(swirlTime)) * 0.1;
  flow += noise(uv * 0.5 + swirlOffset + t * 0.2) * 0.1;
  
  // Final color refinement
  color = mix(color, vec3(0.0), smoothstep(0.7, 1.0, length(uv)));
  color = pow(color, vec3(1.2));

  gl_FragColor = vec4(color, 1.0);
}