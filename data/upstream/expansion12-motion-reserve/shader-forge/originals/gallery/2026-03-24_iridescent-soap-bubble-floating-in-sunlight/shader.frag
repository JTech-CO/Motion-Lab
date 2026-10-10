uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple hash & noise
float hash(float n) { return fract(sin(n) * 43758.5453); }
float noise(vec3 x) {
  vec3 p = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  float n = p.x + p.y * 57.0 + p.z * 289.0;
  float c0 = hash(n + 0.0), c1 = hash(n + 1.0), c2 = hash(n + 57.0), c3 = hash(n + 58.0);
  float c4 = hash(n + 289.0), c5 = hash(n + 290.0), c6 = hash(n + 346.0), c7 = hash(n + 347.0);
  return mix(mix(mix(c0, c1, f.x), mix(c2, c3, f.x), f.y),
             mix(mix(c4, c5, f.x), mix(c6, c7, f.x), f.y), f.z);
}

// 3D Simplex noise (simplified)
vec3 simplex(vec3 p) {
  vec3 a = floor(p + dot(p, vec3(0.333333)));
  vec3 p0 = p - a + dot(a, vec3(0.333333));
  vec3 p1 = p0 - (p0.x > p0.y ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0));
  vec3 p2 = p0 - (p0.x > p0.y ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0));
  vec3 p3 = p0 - vec3(1.0, 1.0, 1.0);
  vec3 n = dot(p0, p0) > dot(p1, p1) ? (dot(p1, p1) > dot(p2, p2) ? (dot(p2, p2) > dot(p3, p3) ? p0 : p2) : (dot(p1, p1) > dot(p3, p3) ? p1 : p3)) : (dot(p0, p0) > dot(p2, p2) ? (dot(p0, p0) > dot(p3, p3) ? p0 : p3) : (dot(p0, p0) > dot(p1, p1) ? p0 : p1));
  float w = 0.6 - dot(n, n);
  return vec3(w * w * w * (n.x + n.y + n.z));
}

// SDF for sphere
float sdSphere(vec3 p, float r) { return length(p) - r; }

// Fresnel factor
float fresnel(vec3 v, vec3 n, float F0) {
  return F0 + (1.0 - F0) * pow(1.0 - dot(v, n), 5.0);
}

// Sky gradient
vec3 getSkyColor(vec3 dir) {
  float y = dir.y;
  vec3 sky = mix(vec3(0.1, 0.3, 0.6), vec3(0.9, 0.8, 0.6), smoothstep(0.0, 0.5, y));
  return sky;
}

// Sun disc
float getSun(vec3 dir, vec3 sunDir) {
  float d = dot(dir, sunDir);
  return smoothstep(0.02, 0.0, d);
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  vec2 uv2 = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
  
  // Camera ray
  vec3 ro = vec3(0.0, 0.0, 3.5);
  vec3 rd = normalize(vec3(uv2, -1.0));
  
  // Sun direction
  vec3 sunDir = normalize(vec3(sin(uTime * 0.3), cos(uTime * 0.2), -0.5));
  
  // Raymarch sphere
  float t = 0.0;
  float r = 0.45;
  vec3 p, n;
  
  for (int i = 0; i < 128; i++) {
    p = ro + t * rd;
    float d = sdSphere(p, r);
    if (d < 0.001) break;
    t += d;
    if (t > 5.0) { gl_FragColor = vec4(getSkyColor(rd), 1.0); return; }
  }
  
  // Surface normal
  n = normalize(p);
  
  // View vector
  vec3 v = normalize(ro - p);
  
  // Fresnel for iridescence
  float f = fresnel(v, n, 0.02);
  
  // Iridescence: thin-film interference approximation
  float path = 2.0 * dot(n, v) * r;
  float wave = 0.5 + 0.5 * sin(path * 20.0 + uTime * 2.0);
  vec3 irid = mix(vec3(0.1, 0.7, 0.9), vec3(0.9, 0.7, 0.1), wave);
  irid *= exp(-abs(path - 0.6) * 8.0);
  
  // Environment reflection
  vec3 reflectDir = reflect(-v, n);
  vec3 envColor = mix(getSkyColor(reflectDir), vec3(1.0, 0.9, 0.8) * getSun(reflectDir, sunDir), 0.3);
  
  // Specular highlight
  vec3 l = normalize(vec3(0.0, 1.0, 1.0));
  vec3 h = normalize(v + l);
  float spec = pow(max(dot(n, h), 0.0), 64.0);
  
  // Shadow from sun
  float shadow = smoothstep(0.0, 0.3, dot(n, sunDir));
  
  // Final color
  vec3 color = vec3(0.0);
  color += irid * 0.8;
  color += envColor * (1.0 - f) * 0.7;
  color += vec3(1.0) * spec * 0.5;
  color += envColor * shadow * 0.3;
  color += vec3(0.8, 0.7, 0.6) * getSun(rd, sunDir) * 0.4;
  
  // Chromatic aberration (subtle) - use offset UVs instead of texture sampling
  float ca = length(uv2) * 0.03;
  vec3 colorR = vec3(0.0);
  vec3 colorB = vec3(0.0);
  
  // Red channel offset
  {
    vec2 offset = uv + vec2(ca, 0.0);
    float aspect2 = uResolution.x / uResolution.y;
    vec2 uv2R = vec2((offset.x - 0.5) * aspect2, offset.y - 0.5);
    vec3 rdR = normalize(vec3(uv2R, -1.0));
    float tR = 0.0;
    vec3 pR;
    
    for (int i = 0; i < 128; i++) {
      pR = ro + tR * rdR;
      float d = sdSphere(pR, r);
      if (d < 0.001) break;
      tR += d;
      if (tR > 5.0) break;
    }
    
    if (tR <= 5.0) {
      vec3 nR = normalize(pR);
      vec3 vR = normalize(ro - pR);
      float fR = fresnel(vR, nR, 0.02);
      float pathR = 2.0 * dot(nR, vR) * r;
      float waveR = 0.5 + 0.5 * sin(pathR * 20.0 + uTime * 2.0);
      vec3 iridR = mix(vec3(0.1, 0.7, 0.9), vec3(0.9, 0.7, 0.1), waveR);
      iridR *= exp(-abs(pathR - 0.6) * 8.0);
      colorR = iridR * 0.8;
    } else {
      colorR = getSkyColor(rdR);
    }
  }
  
  // Blue channel offset
  {
    vec2 offset = uv + vec2(-ca, 0.0);
    float aspect2 = uResolution.x / uResolution.y;
    vec2 uv2B = vec2((offset.x - 0.5) * aspect2, offset.y - 0.5);
    vec3 rdB = normalize(vec3(uv2B, -1.0));
    float tB = 0.0;
    vec3 pB;
    
    for (int i = 0; i < 128; i++) {
      pB = ro + tB * rdB;
      float d = sdSphere(pB, r);
      if (d < 0.001) break;
      tB += d;
      if (tB > 5.0) break;
    }
    
    if (tB <= 5.0) {
      vec3 nB = normalize(pB);
      vec3 vB = normalize(ro - pB);
      float fB = fresnel(vB, nB, 0.02);
      float pathB = 2.0 * dot(nB, vB) * r;
      float waveB = 0.5 + 0.5 * sin(pathB * 20.0 + uTime * 2.0);
      vec3 iridB = mix(vec3(0.1, 0.7, 0.9), vec3(0.9, 0.7, 0.1), waveB);
      iridB *= exp(-abs(pathB - 0.6) * 8.0);
      colorB = iridB * 0.8;
    } else {
      colorB = getSkyColor(rdB);
    }
  }
  
  color = vec3(colorR.r, color.g, colorB.b) * 0.3 + color * 0.7;
  
  // Vignette
  float vig = 1.0 - dot(uv2, uv2) * 0.8;
  color *= smoothstep(0.5, 1.0, vig);
  
  // Tone mapping
  color = color / (color + 1.0);
  
  gl_FragColor = vec4(color, 1.0);
}