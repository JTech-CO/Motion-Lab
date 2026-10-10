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

// Helper functions for colorful gradient waves

fn hash(p: vec2f) -> f32 {
    return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453123);
}

fn noise(p: vec2f) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    
    let a = hash(i + vec2f(0.0, 0.0));
    let b = hash(i + vec2f(1.0, 0.0));
    let c = hash(i + vec2f(0.0, 1.0));
    let d = hash(i + vec2f(1.0, 1.0));
    
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f, octaves: i32) -> f32 {
    var value = 0.0;
    var amplitude = 0.5;
    var frequency = 1.0;
    
    for (var i = 0; i < octaves; i++) {
        value += amplitude * noise(p * frequency);
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    return value;
}

fn domainWarp(p: vec2f, t: f32) -> vec2f {
    let n = noise(p * 2.0 + t * 0.3);
    return p + vec2f(n * 0.3, noise(p.yx * 2.0 + t * 0.3) * 0.3);
}

fn cosPalette(t: f32) -> vec3f {
    return 0.5 + 0.5 * cos(t + vec3f(0.0, 2.0, 4.0));
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
    let uv = in.uv;
    
    // Aspect correction and centering
    let aspect = u.resolution.x / u.resolution.y;
    var uvCentered = uv;
    uvCentered.x *= aspect;
    uvCentered = (uvCentered - 0.5) * 2.0;
    
    // Time-based animation speed
    let t = u.time * 0.4;
    
    // Domain-warp the UV coordinates for organic movement
    let warped = domainWarp(uvCentered, t);
    
    // Layered FBM for rich wave patterns
    let baseWave = fbm(warped * 1.5, 4);
    let detailWave = fbm(warped * 3.0 + t * 0.2, 3) * 0.3;
    
    // Combine waves and scale for color palette
    let waveValue = baseWave + detailWave;
    let paletteInput = waveValue * 10.0 + t * 0.5;
    
    // Get vibrant colors from cosine palette
    var color = cosPalette(paletteInput);
    
    // Add subtle contrast enhancement
    color = mix(color, vec3f(0.0), 0.1);
    
    // Soft radial gradient for brightness falloff
    let dist = length(uvCentered);
    let vignette = 1.0 - smoothstep(0.8, 1.2, dist);
    color *= 0.7 + 0.3 * vignette;
    
    // Gentle brightness boost
    color *= 1.2;
    
    // Soft edge fade for smooth transitions
    let edgeFade = smoothstep(0.0, 1.0, uv.y) * (1.0 - smoothstep(0.0, 1.0, 1.0 - uv.y));
    color *= 0.8 + 0.2 * edgeFade;
    
    return vec4f(color, 1.0);
}