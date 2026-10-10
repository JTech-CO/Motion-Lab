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

// Helper functions for plasma energy field

fn hash(n: f32) -> f32 {
    return fract(sin(n) * 43758.5453123);
}

fn hash2(p: vec2f) -> f32 {
    return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453123);
}

fn noise(p: vec2f) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    
    let a = hash(i.x + i.y * 57.0);
    let b = hash(i.x + 1.0 + i.y * 57.0);
    let c = hash(i.x + (i.y + 1.0) * 57.0);
    let d = hash(i.x + 1.0 + (i.y + 1.0) * 57.0);
    
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f, octaves: f32) -> f32 {
    var value = 0.0;
    var amplitude = 0.5;
    var frequency = 1.0;
    
    for (var i = 0u; i < 6u; i++) {
        value += noise(p * frequency) * amplitude;
        frequency *= 2.0;
        amplitude *= 0.5;
        if (i >= u32(octaves - 1.0)) {
            break;
        }
    }
    return value;
}

fn plasmaColor(t: f32) -> vec3f {
    // Vibrant palette using sine waves for smooth color transitions
    let r = 0.5 + 0.5 * sin(t * 1.0 + 0.0);
    let g = 0.5 + 0.5 * sin(t * 1.0 + 2.094);
    let b = 0.5 + 0.5 * sin(t * 1.0 + 4.188);
    return vec3f(r, g, b);
}

fn vibrantPalette(base: vec3f, t: f32) -> vec3f {
    // Add hue cycling and boost saturation
    let hueCycle = vec3f(
        sin(t * 0.5 + 0.0),
        sin(t * 0.5 + 2.094),
        sin(t * 0.5 + 4.188)
    );
    
    // Mix base with vibrant colors
    let vibrant = mix(base, vec3f(0.5) + 0.5 * hueCycle, 0.7);
    
    // Boost brightness and contrast
    let boosted = pow(vibrant, vec3f(0.7)) * 1.3;
    
    return clamp(boosted, vec3f(0.0), vec3f(1.0));
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
    let uv = in.uv;
    let t = u.time * 0.8;
    
    // Fix aspect ratio
    let aspect = u.resolution.x / u.resolution.y;
    var uvw = uv;
    uvw.x *= aspect;
    
    // Center UVs for radial effects
    var p = uvw - 0.5;
    p.x *= aspect;
    
    var color = vec3f(0.0);
    
    // Plasma energy field layers
    for (var i = 0u; i < 5u; i++) {
        let layer = f32(i);
        
        // Domain warping parameters per layer
        let scale = 1.0 + layer * 0.6;
        let speed = 0.5 + layer * 0.3;
        let warpAmount = 0.3 + layer * 0.15;
        
        // Create swirling motion
        let angle = t * speed + layer * 1.57;
        let rotMat = mat2x2f(
            vec2f(cos(angle), -sin(angle)),
            vec2f(sin(angle), cos(angle))
        );
        
        // Rotated and scaled coordinates
        var pw = p * scale;
        pw = rotMat * pw;
        
        // Add domain warping
        let nx = noise(pw * 2.0 + vec2f(t * 0.3, 0.0)) * warpAmount;
        let ny = noise(pw * 2.0 + vec2f(0.0, t * 0.3)) * warpAmount;
        pw += vec2f(nx, ny);
        
        // Create plasma bands with sine waves
        let wave1 = sin(pw.x * 3.0 + t * speed + layer * 2.0);
        let wave2 = sin(pw.y * 2.5 - t * (speed * 0.8) + layer * 1.5);
        let wave3 = noise(pw * 1.5 + t * 0.2) * 0.5;
        
        let plasmaValue = (wave1 + wave2 + wave3) * 0.5 + 0.5;
        
        // Soft glow falloff
        let glow = pow(plasmaValue, 2.0) * (1.0 - layer * 0.15);
        
        // Layer color based on time and layer index
        let layerColor = plasmaColor(t * 0.3 + layer * 0.7);
        
        // Add to total color with intensity
        color += layerColor * glow * 0.8;
    }
    
    // Add subtle radial gradient for depth
    let dist = length(p);
    let radial = smoothstep(1.2, 0.2, dist);
    color *= radial * 0.7 + 0.3;
    
    // Add high-frequency micro-noise for energy texture
    let microNoise = noise(vec2f(uvw.x * 15.0 + t, uvw.y * 15.0 - t)) * 0.15;
    color += vec3f(microNoise);
    
    // Apply vibrant palette transformation
    color = vibrantPalette(color, t);
    
    // Final tone mapping to prevent blowout
    color = color / (color + 1.0) * 1.2;
    
    // Add subtle vignette
    let vig = 1.0 - length(uvw - 0.5) * 0.5;
    color *= smoothstep(0.0, 1.0, vig);
    
    return vec4f(color, 1.0);
}