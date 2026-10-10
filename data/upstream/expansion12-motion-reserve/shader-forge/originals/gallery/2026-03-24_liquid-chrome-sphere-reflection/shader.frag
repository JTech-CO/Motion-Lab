uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(float n) { return fract(sin(n) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float n = i.x + i.y * 57.0;
  return mix(mix(hash(n), hash(n + 1.0), f.x),
             mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  vec2 offset = vec2(0.0);
  for (int i = 0; i < 5; i++) {
    v += a * noise(p + offset);
    p *= 2.0;
    a *= 0.5;
    offset += vec2(100.0);
  }
  return v;
}

float sdSphere(vec3 p, float r) {
  return length(p) - r;
}

float map(vec3 p) {
  float t = uTime * 0.4;
  vec3 q = p;
  q.xz *= mat2(cos(t*0.3), -sin(t*0.3), sin(t*0.3), cos(t*0.3));
  float d = sdSphere(q, 0.8);
  
  // Liquid blobs
  float w1 = sin(t + p.y * 2.0) * 0.3;
  float w2 = cos(t * 0.7 + p.x * 1.5) * 0.2;
  float w3 = sin(t * 1.3 + p.z * 1.2) * 0.2;
  d += (w1 + w2 + w3) * 0.2;
  
  // Detail ripples
  d += fbm(p.xy * 4.0 + t) * 0.03;
  return d;
}

vec3 calcNormal(vec3 p) {
  vec2 e = vec2(0.001, 0.0);
  return normalize(vec3(
    map(p + e.xyy) - map(p - e.xyy),
    map(p + e.yxy) - map(p - e.yxy),
    map(p + e.yyx) - map(p - e.yyx)
  ));
}

void main() {
  vec2 uv = (vUv - 0.5) * 2.0;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;
  
  vec3 ro = vec3(0.0, 0.0, 2.5);
  vec3 rd = normalize(vec3(uv, -1.2));
  
  float t = 0.0;
  float d;
  for (int i = 0; i < 60; i++) {
    vec3 p = ro + rd * t;
    d = map(p);
    if (d < 0.001 || t > 10.0) break;
    t += d;
  }
  
  vec3 color = vec3(0.02, 0.02, 0.04);
  
  if (d < 0.001) {
    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    vec3 viewDir = normalize(ro - p);
    
    // Metallic reflection
    vec3 refl = reflect(-viewDir, n);
    
    // Iridescent highlights
    float irid = dot(n, viewDir);
    vec3 iridColor = vec3(
      sin(irid * 10.0 + uTime) * 0.5 + 0.5,
      sin(irid * 10.0 + uTime + 2.094) * 0.5 + 0.5,
      sin(irid * 10.0 + uTime + 4.189) * 0.5 + 0.5
    );
    
    // Environment approximation using noise
    float env = fbm(refl.xy * 3.0 + uTime * 0.2) * 0.6 + 0.4;
    
    // Specular
    vec3 lightDir = normalize(vec3(1.0, 1.5, 1.0));
    float spec = pow(max(dot(n, normalize(lightDir + viewDir)), 0.0), 120.0);
    
    // Diffuse + ambient
    float diff = max(dot(n, lightDir), 0.0);
    
    // Base metallic color
    vec3 base = vec3(0.6, 0.65, 0.7);
    
    // Compose
    color = base * (diff * 0.5 + 0.3);
    color += vec3(env) * spec * 2.0;
    color += iridColor * spec * 0.8;
    color += vec3(0.9, 0.95, 1.0) * pow(spec, 2.0) * 0.8;
    
    // Fresnel rim
    float fresnel = pow(1.0 - max(dot(n, viewDir), 0.0), 4.0);
    color += vec3(0.6, 0.7, 0.9) * fresnel * 0.6;
  }
  
  // Vignette
  float vig = 1.0 - length(vUv - 0.5) * 0.6;
  color *= vig;
  
  gl_FragColor = vec4(color, 1.0);
}