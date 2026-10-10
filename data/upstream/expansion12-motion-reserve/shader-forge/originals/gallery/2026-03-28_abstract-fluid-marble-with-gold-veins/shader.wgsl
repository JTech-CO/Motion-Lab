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

// Helper functions for noise and fluid simulation

fn hash(p: vec2f) -> f32 {
  let h = dot(p, vec2f(127.1, 311.7));
  return fract(sin(h) * 43758.5453123);
}

fn noise(p: vec2f) -> f32 {
  let i = vec2f(floor(p));
  let f = vec2f(fract(p));
  let u = f * f * (3.0 - 2.0 * f);

  let a = hash(i);
  let b = hash(i + vec2f(1.0, 0.0));
  let c = hash(i + vec2f(0.0, 1.0));
  let d = hash(i + vec2f(1.0, 1.0));

  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f) -> f32 {
  var f: f32 = 0.0;
  var w: f32 = 0.5;
  var s: f32 = 1.0;
  for (var i = 0u; i < 6u; i++) {
    f += w * noise(p * s);
    s *= 2.0;
    w *= 0.5;
  }
  return f;
}

// Curl noise for divergence-free flow field
fn curl(p: vec2f, t: f32) -> vec2f {
  let eps: f32 = 0.001;
  let tOffset = t * 0.5;
  
  // Create rotational field from scalar noise potential
  let n1 = noise(p + vec2f(0.0, tOffset));
  let n2 = noise(p + vec2f(eps, tOffset));
  let n3 = noise(p + vec2f(0.0, eps + tOffset));
  let n4 = noise(p + vec2f(eps, eps + tOffset));
  
  // Partial derivatives for curl operation
  let dy = (n2 - n1) / eps;
  let dx = (n3 - n1) / eps;
  
  // Rotate gradient to get perpendicular (curl) direction
  return vec2f(-dy, dx);
}

// Smooth minimum for blending
fn smin(a: f32, b: f32, k: f32) -> f32 {
  let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  return mix(b, a, h) - k * h * (1.0 - h);
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
  let uv = in.uv;
  let t = u.time * 0.4;
  
  // Aspect correction
  let aspect = u.resolution.x / u.resolution.y;
  var uvw = uv;
  uvw.x *= aspect;
  uvw = uvw * 2.0 - 1.0; // Center at origin
  
  // Domain warping with curl flow
  var p = uvw;
  for (var i = 0u; i < 3u; i++) {
    let flow = curl(p * 0.8, t) * 0.3;
    p += flow;
  }
  
  // Base FBM for fluid structure
  let baseFbm = fbm(p * 2.0 + vec2f(t * 0.2, -t * 0.1));
  
  // Create gold veins with high-contrast FBM
  let veinPattern = fbm(p * 4.0 + vec2f(t * 0.4, t * 0.3));
  
  // Enhance veins with power function for contrast
  let veinStrength = pow(clamp(veinPattern, 0.0, 1.0), 10.0);
  
  // Base gold color
  var color = mix(vec3f(1.0, 0.85, 0.3), vec3f(1.0, 0.6, 0.1), baseFbm * 0.7 + 0.3);
  
  // Add gold veins
  color += vec3f(1.0, 0.8, 0.2) * veinStrength * 1.5;
  
  // Add subtle white highlights at vein intersections
  let highlight = pow(veinPattern, 16.0);
  color += vec3f(1.0) * highlight * 0.8;
  
  // Add secondary FBM layer for depth
  let depthFbm = fbm(p * 8.0 + vec2f(t * 0.1, -t * 0.2));
  color += vec3f(0.8, 0.6, 0.2) * depthFbm * 0.3;
  
  // Add iridescence based on position and time
  let iridescence = sin(dot(p, vec2f(5.0)) + t * 2.0) * 0.15;
  color += vec3f(0.3, 0.5, 0.8) * iridescence;
  
  // Vignette for depth
  let dist = length(uvw);
  let vig = 1.0 - smoothstep(0.5, 1.2, dist);
  color *= vig;
  
  // Tone mapping for vibrant colors
  color = color / (color + 1.0) * 1.2;
  
  return vec4f(color, 1.0);
}