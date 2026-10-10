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

// Hash noise function (1D)
fn hash1(n: f32) -> f32 {
  return fract(sin(n) * 43758.5453123);
}

// 2D noise function
fn noise(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  
  let a = hash1(dot(i, vec2f(1.0, 57.0)));
  let b = hash1(dot(i + vec2f(1.0, 0.0), vec2f(1.0, 57.0)));
  let c = hash1(dot(i + vec2f(0.0, 1.0), vec2f(1.0, 57.0)));
  let d = hash1(dot(i + vec2f(1.0, 1.0), vec2f(1.0, 57.0)));
  
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Smooth glow falloff
fn glow(d: f32, strength: f32) -> f32 {
  return exp(-d * (8.0 / strength));
}

// Sun bands pattern
fn sunBands(y: f32, t: f32) -> f32 {
  let bands = step(0.5, fract(y * 25.0 + t * 0.3));
  return mix(1.0, 0.4, bands);
}

// Grid glow with perspective
fn gridGlow(p: vec2f, t: f32, horizon: f32) -> vec2f {
  // Perspective transform
  let groundY = horizon - p.y;
  let depth = 0.3 / max(groundY, 0.001);
  
  // Grid coordinates with scrolling
  let gridX = p.x * depth;
  let gridY = depth + t * 4.0;
  
  // Grid line distances
  let lineX = abs(fract(gridX) - 0.5);
  let lineY = abs(fract(gridY * 0.5) - 0.5);
  
  // Add subtle wave distortion to grid
  let waveDistort = noise(vec2f(gridY * 0.1, gridX * 0.1)) * 0.05;
  let distortedLineX = abs(fract(gridX + waveDistort) - 0.5);
  
  // Main grid lines
  let gridLineX = glow(distortedLineX, 0.5);
  let gridLineY = glow(lineY, 0.5);
  
  // Accent every 4th line
  let accentX = glow(abs(fract(gridX * 0.25) - 0.5), 0.3) * 0.4;
  let accentY = glow(abs(fract(gridY * 0.125) - 0.5), 0.3) * 0.4;
  
  return vec2f(gridLineX + gridLineY, accentX + accentY);
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
  let uv = in.uv;
  let t = u.time;
  let aspect = u.resolution.x / u.resolution.y;
  
  // Remap UV: center origin, aspect correct
  let p = vec2f((uv.x - 0.5) * aspect, uv.y - 0.5);
  
  // Horizon line at y = 0.15 (slightly above center)
  let horizon = 0.15;
  
  // Base colors
  let skyColor = vec3f(0.02, 0.01, 0.08);
  let gridColor = vec3f(0.0, 0.8, 1.0);
  let accentColor = vec3f(1.0, 0.2, 0.8);
  let sunColor = vec3f(1.0, 0.9, 0.3);
  
  var color = skyColor;
  
  // ---- Sky / horizon glow ----
  let horizonGlow = exp(-abs(p.y - horizon) * 12.0) * 0.6;
  color += accentColor * horizonGlow * 1.5;
  
  // ---- Sun circle at horizon ----
  let sunCenter = vec2f(0.0, horizon + 0.12);
  let sunDist = length(p - sunCenter);
  let sunBase = smoothstep(0.12, 0.115, sunDist);
  
  // Sun bands (horizontal lines through sun)
  let sunBandsVal = sunBands(p.y, t);
  let sun = sunBase * sunBandsVal;
  
  // Sun glow
  let sunGlow = exp(-sunDist * 8.0) * 0.4;
  
  // Sun color mixing
  let sunFinal = mix(sunColor, accentColor, 0.3);
  color += sunFinal * sun * 2.0;
  color += sunFinal * sunGlow * 2.5;
  
  // Sun pulse animation
  let sunPulse = 1.0 + sin(t * 0.5) * 0.1;
  color *= sunPulse;
  
  // ---- Ground grid (below horizon) ----
  if (p.y < horizon) {
    let groundY = horizon - p.y;
    let gridData = gridGlow(p, t * 0.8, horizon);
    let gridLine = gridData.x;
    let accentLine = gridData.y;
    
    // Fade with distance
    let distFade = exp(-groundY * 3.0);
    
    // Perspective sharpening
    let sharpness = mix(40.0, 8.0, smoothstep(0.0, 0.4, groundY));
    let gridLineFinal = glow(gridLine, sharpness * 0.5);
    let accentLineFinal = glow(accentLine, sharpness * 0.3) * 0.4;
    
    // Grid color composition
    let gridColorFinal = gridColor * (gridLineFinal + gridLineFinal * 0.5) * distFade;
    let accentColorFinal = accentColor * (accentLineFinal + accentLineFinal * 0.3) * distFade;
    
    // Depth fog tint
    let fogTint = mix(vec3f(1.0), gridColor * 0.3, smoothstep(0.0, 0.35, groundY));
    
    color += (gridColorFinal + accentColorFinal) * fogTint;
  }
  
  // ---- Vertical side lines (pillars fading up) ----
  let sideGlow = exp(-abs(abs(p.x) - aspect * 0.48) * 30.0) * 0.2;
  let sideFade = smoothstep(horizon + 0.3, horizon - 0.2, p.y);
  color += gridColor * sideGlow * sideFade * 1.5;
  
  // ---- Aurora waves in sky ----
  let auroraY = 0.3 + noise(vec2f(p.x * 0.5 + t * 0.2, t * 0.1)) * 0.2;
  let auroraDist = abs(p.y - auroraY);
  let auroraGlow = exp(-auroraDist * auroraDist * 30.0) * 0.4;
  color += mix(vec3f(0.3, 0.1, 0.6), accentColor, 0.5) * auroraGlow;
  
  // ---- Vignette ----
  let vignette = 1.0 - dot(uv - 0.5, uv - 0.5) * 1.8;
  let vig = clamp(vignette, 0.0, 1.0);
  color *= vig;
  
  // ---- Tone mapping to prevent blowout ----
  color = min(color, vec3f(2.0));
  
  return vec4f(color, 1.0);
}