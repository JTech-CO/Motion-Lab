uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Simple hash for noise
float hash(float n) { return fract(sin(n * 12.9898) * 43758.5453); }

// 2D noise
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float n = i.x + i.y * 57.0;
  return mix(mix(hash(n), hash(n + 1.0), f.x),
             mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y);
}

// Value noise for smoother patterns
float pnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float n = i.x + i.y * 57.0;
  return mix(mix(hash(n), hash(n + 1.0), f.x),
             mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y);
}

// Simplex-like noise
vec2 rotate(vec2 p, float a) {
  float s = sin(a);
  float c = cos(a);
  return vec2(p.x * c - p.y * s, p.x * s + p.y * c);
}

// Voronoi for stained glass
vec3 voronoi(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  
  float minDist = 1.0;
  vec2 minPoint = vec2(0.0);
  
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 cell = vec2(float(x), float(y));
      vec2 point = vec2(hash(i.x + cell.x + 100.0 * (i.y + cell.y)), 
                       hash(i.x + cell.x + 200.0 * (i.y + cell.y)));
      vec2 diff = point - f;
      float dist = length(diff);
      
      if (dist < minDist) {
        minDist = dist;
        minPoint = point;
      }
    }
  }
  
  // Get secondary nearest neighbor for border definition
  float secondMin = 1.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 cell = vec2(float(x), float(y));
      vec2 point = vec2(hash(i.x + cell.x + 100.0 * (i.y + cell.y)), 
                       hash(i.x + cell.x + 200.0 * (i.y + cell.y)));
      vec2 diff = point - f;
      float dist = length(diff);
      
      if (dist < secondMin && dist > minDist + 0.01) {
        secondMin = dist;
      }
    }
  }
  
  return vec3(minPoint, secondMin - minDist);
}

vec3 ACESFilm(vec3 color) {
  color *= 0.6;
  vec3 a = color * (color + 0.0245786) - 0.000090537;
  vec3 b = color * (0.983729 * color + 0.4329510) + 0.238081;
  return clamp(a / b, 0.0, 1.0);
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  
  // Center and scale UVs
  vec2 uvCentered = (uv - 0.5) * vec2(aspect, 1.0);
  
  // Time-based rotation for stained glass
  float rotation = uTime * 0.05;
  uvCentered = rotate(uvCentered, rotation);
  
  // Voronoi pattern for stained glass
  vec3 vor = voronoi(uvCentered * 8.0 + uTime * 0.2);
  vec3 cellColor = vec3(hash(vor.x * 123.0 + vor.y * 456.0), 
                        hash(vor.x * 234.0 + vor.y * 567.0), 
                        hash(vor.x * 345.0 + vor.y * 678.0));
  
  // Color palette for stained glass
  cellColor = clamp(cellColor * vec3(1.2, 1.0, 1.3), 0.0, 1.0);
  cellColor = mix(cellColor, cellColor * vec3(0.8, 1.2, 1.0), 0.3);
  
  // Border thickness and softness
  float border = smoothstep(0.02, 0.05, vor.z);
  
  // Base stained glass color
  vec3 color = mix(cellColor * 0.9, vec3(0.0), border * 0.8);
  
  // Volumetric god rays
  vec2 lightDir = normalize(vec2(0.5, 0.7) - uv);
  float distToLight = length(uv - vec2(0.5, 0.7));
  float godRay = exp(-distToLight * 8.0) * sin(uvCentered.x * 20.0 + uTime * 2.0);
  godRay = clamp(godRay * 0.3, 0.0, 1.0);
  
  // Dust particles
  float dust = noise(uv * 40.0 + uTime * 0.5) * 0.1;
  dust *= exp(-distToLight * 5.0);
  
  // Add light leak at bottom
  float lightLeak = smoothstep(0.0, 0.3, uv.y) * 0.4 * (1.0 - uv.x * (1.0 - uv.x) * 4.0);
  lightLeak *= 0.8 + 0.2 * sin(uTime * 0.3);
  
  // Combine effects
  color += vec3(1.0, 0.85, 0.6) * godRay;
  color += vec3(1.0) * dust;
  color += vec3(0.9, 0.7, 0.5) * lightLeak;
  
  // Add some texture/noise to avoid banding
  color += vec3(pnoise(uv * 100.0) * 0.02);
  
  // ACES tonemapping
  color = ACESFilm(color);
  
  gl_FragColor = vec4(color, 1.0);
}