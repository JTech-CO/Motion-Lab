struct Uniforms { time: f32, resolution: vec2f, _pad: f32 }
@group(0) @binding(0) var<uniform> u: Uniforms;

struct VSOut { @builtin(position) pos: vec4f, @location(0) uv: vec2f }

@vertex fn vs(@builtin(vertex_index) vi: u32) -> VSOut {
  let p = array(vec2f(-1,-1), vec2f(1,-1), vec2f(-1,1), vec2f(-1,1), vec2f(1,-1), vec2f(1,1));
  var o: VSOut;
  o.pos = vec4f(p[vi], 0, 1);
  o.uv = p[vi] * 0.5 + 0.5;
  return o;
}

// Helper functions

fn hash(x: f32) -> f32 {
  return fract(sin(x) * 43758.5453123);
}

fn noise(p: vec2f) -> f32 {
  let i = vec2f(floor(p));
  let f = p - i;
  let u = f * f * (3.0 - 2.0 * f);
  
  let n = i.x + i.y * 57.0;
  let a = hash(n);
  let b = hash(n + 1.0);
  let c = hash(n + 57.0);
  let d = hash(n + 58.0);
  
  let x1 = mix(a, b, u.x);
  let x2 = mix(c, d, u.x);
  
  return mix(x1, x2, u.y);
}

// 3D noise for curl computation
fn noise3(p: vec3f) -> f32 {
  let i = vec3f(floor(p));
  let f = p - i;
  let u = f * f * (3.0 - 2.0 * f);
  
  let n = i.x + i.y * 57.0 + i.z * 113.0;
  let a = hash(n);
  let b = hash(n + 1.0);
  let c = hash(n + 57.0);
  let d = hash(n + 58.0);
  let e = hash(n + 113.0);
  let f_val = hash(n + 114.0);
  let g = hash(n + 170.0);
  let h = hash(n + 171.0);
  
  let x1 = mix(a, b, u.x);
  let x2 = mix(c, d, u.x);
  let x3 = mix(e, f_val, u.x);
  let x4 = mix(g, h, u.x);
  
  let y1 = mix(x1, x2, u.y);
  let y2 = mix(x3, x4, u.y);
  
  return mix(y1, y2, u.z);
}

// Curl noise: 2D vector field from 3D noise gradient cross product
fn curlNoise(p: vec2f, t: f32) -> vec2f {
  // Rotate input for vortex effect
  let angle = t * 0.5;
  let rot = mat2x2f(
    cos(angle), -sin(angle),
    sin(angle), cos(angle)
  );
  let rp = rot * p;
  
  // Add time evolution
  let z = t * 0.3;
  
  // Small epsilon for numerical stability
  let eps = 0.001;
  
  // Compute curl using finite differences of 3D noise
  let n0 = noise3(vec3f(rp.x, rp.y, z));
  let nx = noise3(vec3f(rp.x + eps, rp.y, z));
  let ny = noise3(vec3f(rp.x, rp.y + eps, z));
  let nz = noise3(vec3f(rp.x, rp.y, z + eps));
  
  // Curl = ∇ × (0, 0, noise) = (dnoise/dy, -dnoise/dx)
  let dx = (nx - n0) / eps;
  let dy = (ny - n0) / eps;
  
  return vec2f(dy, -dx);
}

// Plasma color function with 3 sine layers
fn plasmaColor(p: vec2f, t: f32) -> vec3f {
  // Base colors
  let colorA = vec3f(0.1, 0.0, 0.6);
  let colorB = vec3f(0.9, 0.1, 0.1);
  let colorC = vec3f(0.0, 0.9, 0.9);
  
  var color = vec3f(0.0);
  
  // Layer 1: Slow, large waves
  let layer1 = sin(p.x * 2.0 + t * 0.6) * 0.5 +
               cos(p.y * 1.5 + t * 0.4) * 0.5 +
               noise(p * 1.5) * 0.3;
  
  // Layer 2: Medium waves
  let layer2 = sin(p.x * 3.5 - t * 0.8) * 0.4 +
               cos(p.y * 2.5 - t * 0.5) * 0.4 +
               noise(p * 2.5 + vec2f(t * 0.3, -t * 0.2)) * 0.25;
  
  // Layer 3: Fast, fine details
  let layer3 = sin(p.x * 5.0 + t * 1.2) * 0.3 +
               cos(p.y * 4.0 + t * 0.9) * 0.3 +
               noise(p * 4.0 + vec2f(t, t * 0.5)) * 0.2;
  
  // Combine layers with different color mixes
  let mix1 = (layer1 + 1.0) * 0.5;
  let mix2 = (layer2 + 1.0) * 0.5;
  let mix3 = (layer3 + 1.0) * 0.5;
  
  // Color interpolation
  color += mix(colorA, colorB, mix1) * 0.4;
  color += mix(colorB, colorC, mix2) * 0.35;
  color += mix(colorC, colorA, mix3) * 0.25;
  
  // Boost contrast and saturation
  color = clamp(color, vec3f(0.0), vec3f(1.0));
  color = pow(color * 1.2, vec3f(1.1));
  
  return color;
}

// Bloom falloff function
fn bloom(p: vec2f) -> f32 {
  let dist = length(p);
  return exp(-dist * 2.5);
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
  let uv = in.uv;
  let t = u.time * 0.8;
  
  // Aspect correction and centering
  let aspect = u.resolution.x / u.resolution.y;
  var p = (uv - 0.5) * 2.0;
  p.x *= aspect;
  
  // Curl noise displacement field
  let curl = curlNoise(p, t);
  
  // Displace coordinates with curl field (vortex effect)
  let displaced = p + curl * 0.3;
  
  // Evaluate plasma color at displaced position
  var color = plasmaColor(displaced, t);
  
  // Add radial bloom
  let bloomVal = bloom(p);
  let bloomColor = vec3f(0.8, 0.6, 1.0) * bloomVal * 0.6;
  color += bloomColor;
  
  // Add subtle center glow
  let centerGlow = exp(-length(p) * 1.5) * 0.3;
  color += vec3f(1.0, 0.8, 0.6) * centerGlow;
  
  // Vignette for depth
  let vignette = 1.0 - length(uv - 0.5) * 0.8;
  color *= vignette;
  
  // Tone mapping to prevent blowout
  color = color / (color + 1.0);
  
  return vec4f(color, 1.0);
}