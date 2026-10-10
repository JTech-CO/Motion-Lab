uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

float hash(float n) {
  return fract(sin(n) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float n = i.x + i.y * 57.0;
  return mix(
    mix(hash(n), hash(n + 1.0), f.x),
    mix(hash(n + 57.0), hash(n + 58.0), f.x),
    f.y
  );
}

float fbm(vec2 p, int octaves) {
  float total = 0.0;
  float amplitude = 0.5;
  float frequency = 1.0;
  for (int i = 0; i < octaves; i++) {
    total += amplitude * noise(p * frequency);
    frequency *= 2.0;
    amplitude *= 0.5;
  }
  return total;
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  uv.x *= aspect;

  float t = uTime * 0.4;

  // Water surface noise
  vec2 noiseUv = uv * 2.0;
  float surfaceNoise = fbm(noiseUv + t * 0.3, 4);
  surfaceNoise += 0.5 * fbm(noiseUv * 2.0 - t * 0.2, 3);
  surfaceNoise = smoothstep(0.3, 0.8, surfaceNoise);

  // Caustic pattern using layered noise
  vec2 causticUv = uv * 8.0;
  float caustic1 = fbm(causticUv + t * 0.5, 3);
  float caustic2 = fbm(causticUv * 1.5 - vec2(t * 0.3, -t * 0.2), 2);
  float caustics = smoothstep(0.4, 0.9, caustic1 + caustic2 * 0.5);
  caustics = pow(caustics, 1.5);

  // Light shafts (volumetric effect approximation)
  float rays = 0.0;
  for (int i = 0; i < 6; i++) {
    float angle = float(i) * 1.047 + t * 0.2;
    vec2 dir = vec2(cos(angle), sin(angle));
    float dist = abs(dot(uv - 0.5, dir));
    rays += smoothstep(0.4, 0.0, dist) * (0.35 - float(i) * 0.05);
  }

  // Fresnel effect at water surface
  vec2 centerDir = normalize(vec2(0.5) - uv);
  float fresnel = pow(1.0 - dot(normalize(vec2(-centerDir.y, centerDir.x)), vec2(0.0, 1.0)), 3.0);
  fresnel = smoothstep(0.0, 0.8, fresnel);

  // Deep ocean color palette
  vec3 deepColor = vec3(0.0, 0.05, 0.15);
  vec3 surfaceColor = vec3(0.0, 0.4, 0.6);
  vec3 lightColor = vec3(0.9, 0.95, 1.0);

  // Combine layers
  vec3 color = deepColor;
  color += surfaceColor * surfaceNoise * 0.4;
  color += lightColor * caustics * 0.8;
  color += lightColor * rays * 0.3;
  color += surfaceColor * fresnel * 0.3;

  // Vignette
  float vig = 1.0 - length(uv - 0.5) * 0.5;
  color *= vig;

  // Tone mapping
  color = color / (color + 0.6);
  
  gl_FragColor = vec4(color, 1.0);
}