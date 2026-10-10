// Helper functions

fn rotY(a: f32) -> mat3x3f {
  let c = cos(a);
  let s = sin(a);
  return mat3x3f(
    vec3f(c, 0.0, -s),
    vec3f(0.0, 1.0, 0.0),
    vec3f(s, 0.0, c)
  );
}

fn rotX(a: f32) -> mat3x3f {
  let c = cos(a);
  let s = sin(a);
  return mat3x3f(
    vec3f(1.0, 0.0, 0.0),
    vec3f(0.0, c, -s),
    vec3f(0.0, s, c)
  );
}

fn sdSphere(p: vec3f, r: f32) -> f32 {
  return length(p) - r;
}

fn smin(a: f32, b: f32, k: f32) -> f32 {
  let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  return mix(b, a, h) - k * h * (1.0 - h);
}

// Ashima 3D Simplex Noise (WebGL1-compatible)
fn mod289_3(x: vec3f) -> vec3f {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

fn mod289_4(x: vec4f) -> vec4f {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

fn permute(x: vec4f) -> vec4f {
  return mod289_4(((x * 34.0) + 10.0) * x);
}

fn taylorInvSqrt(r: vec4f) -> vec4f {
  return 1.79284291400159 - 0.85373472095314 * r;
}

fn snoise(v: vec3f) -> f32 {
  let C = vec2f(1.0 / 6.0, 1.0 / 3.0);
  let D = vec4f(0.0, 0.5, 1.0, 2.0);
  
  let i0  = floor(v + vec3f(dot(v, vec3f(C.y, C.y, C.y))));
  let x0 = v - i0 + vec3f(dot(i0, vec3f(C.x, C.x, C.x)));
  
  let g = step(x0.yzx, x0.xyz);
  let l = 1.0 - g;
  
  let i1 = min(g.xyz, l.zxy);
  let i2 = max(g.xyz, l.zxy);
  
  let x1 = x0 - i1 + vec3f(C.x, C.x, C.x);
  let x2 = x0 - i2 + vec3f(C.y, C.y, C.y);
  let x3 = x0 - vec3f(D.y, D.y, D.y);
  
  let i = mod289_3(i0);
  let p = permute(permute(permute(
      i.z + vec4f(0.0, i1.z, i2.z, 1.0)
    + i.y + vec4f(0.0, i1.y, i2.y, 1.0)
    + i.x + vec4f(0.0, i1.x, i2.x, 1.0)
  )));
  
  let n_ = 0.142857142857;
  let ns = n_ * D.wyz - D.xzx;
  
  let j = p - 49.0 * floor(p * ns.z * ns.z);
  let x_ = floor(j * ns.z);
  let y_ = floor(j - 7.0 * x_);
  
  let x = x_ * ns.x + vec4f(ns.y);
  let y = y_ * ns.x + vec4f(ns.y);
  
  let h = 1.0 - abs(x) - abs(y);
  
  let b0 = vec4f(x.xy, y.xy);
  let b1 = vec4f(x.zw, y.zw);
  
  let s0 = floor(b0) * 2.0 + 1.0;
  let s1 = floor(b1) * 2.0 + 1.0;
  
  let sh = -step(h, vec4f(0.0));
  
  let a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  let a1 = b1.xzyw + s1.xzyw * sh.zzww;
  
  let p0 = vec3f(a0.xy, h.x);
  let p1 = vec3f(a0.zw, h.y);
  let p2 = vec3f(a1.xy, h.z);
  let p3 = vec3f(a1.zw, h.w);
  
  let norm = taylorInvSqrt(vec4f(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  
  let p0n = p0 * norm.x;
  let p1n = p1 * norm.y;
  let p2n = p2 * norm.z;
  let p3n = p3 * norm.w;
  
  let m = max(0.6 - vec4f(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), vec4f(0.0));
  let m2 = m * m;
  let m4 = m2 * m2;
  
  return 42.0 * dot(m4, vec4f(dot(p0n, x0), dot(p1n, x1), dot(p2n, x2), dot(p3n, x3)));
}

fn curl(p: vec3f) -> vec3f {
  let e = vec3f(0.001, 0.0, 0.0);
  let n0 = snoise(p + e.yxx);
  let n1 = snoise(p - e.yxx);
  let n2 = snoise(p + e.xyx);
  let n3 = snoise(p - e.xyx);
  let n4 = snoise(p + e.xxy);
  let n5 = snoise(p - e.xxy);
  
  return vec3f(n2 - n3, n4 - n5, n0 - n1);
}

fn calcLighting(p: vec3f, n: vec3f, viewDir: vec3f) -> vec3f {
  let lightDir1 = normalize(vec3f(1.0, 1.5, 2.0));
  let lightDir2 = normalize(vec3f(-0.5, 0.3, -1.0));
  
  let diff1 = max(dot(n, lightDir1), 0.0);
  let diff2 = max(dot(n, lightDir2), 0.0) * 0.3;
  
  let halfDir1 = normalize(lightDir1 + viewDir);
  let halfDir2 = normalize(lightDir2 + viewDir);
  
  let spec1 = pow(max(dot(n, halfDir1), 0.0), 64.0) * 1.5;
  let spec2 = pow(max(dot(n, halfDir2), 0.0), 32.0) * 0.4;
  
  let fresnel = pow(1.0 - max(dot(n, viewDir), 0.0), 3.0);
  
  let envUp = smoothstep(-0.5, 1.0, reflect(-viewDir, n).y) * 0.5 + 0.5;
  
  let irid = dot(n, viewDir);
  let iridColor = vec3f(
    sin(irid * 8.0 + u.time * 0.3) * 0.5 + 0.5,
    sin(irid * 8.0 + u.time * 0.3 + 2.094) * 0.5 + 0.5,
    sin(irid * 8.0 + u.time * 0.3 + 4.189) * 0.5 + 0.5
  );
  
  let baseColor = vec3f(0.85, 0.88, 0.92);
  let accentColor = vec3f(0.15, 0.35, 0.65);
  
  let color = baseColor * (diff1 * 0.6 + diff2 + 0.2);
  color += spec1 + spec2;
  color += accentColor * fresnel * 0.8;
  color += iridColor * fresnel * 0.2;
  color += vec3f(envUp) * 0.15;
  
  return color;
}

@fragment fn fs(in: VSOut) -> @location(0) vec4f {
  let uv = in.uv;
  let t = u.time;
  
  // Aspect-corrected UV (centered, -1..1)
  let aspect = u.resolution.x / u.resolution.y;
  let uvCentered = (uv - 0.5) * 2.0;
  uvCentered.x *= aspect;
  
  // Ray setup
  let ro = vec3f(0.0, 0.0, 3.5);
  let rd = normalize(vec3f(uvCentered, -1.5));
  
  // Ray march
  var tVal: f32 = 0.0;
  var d: f32 = 1e9;
  var hit: bool = false;
  
  for (var i = 0u; i < 64u; i++) {
    let p = ro + rd * tVal;
    
    // Curl flow deformation
    let flow = curl(p * 0.8) * 0.03;
    let pDeformed = p + flow;
    
    // Scene SDF
    let tMod = mod(t * 0.4, 10.0);
    
    // Main blob
    var dist = sdSphere(pDeformed, 0.8);
    
    // Orbiting blobs
    for (var j = 0u; j < 5u; j++) {
      let fi = f32(j);
      let angle = tMod * (0.5 + fi * 0.15) + fi * 1.2566;
      let radius = 0.6 + sin(tMod * 0.5 + fi) * 0.2;
      let blobSize = 0.3 + sin(tMod * 0.7 + fi * 2.0) * 0.1;
      
      let offset = vec3f(
        cos(angle) * radius,
        sin(angle * 0.7 + fi) * radius * 0.6,
        sin(angle) * radius * 0.5
      );
      
      dist = smin(dist, sdSphere(pDeformed - offset, blobSize), 0.4);
    }
    
    // Smooth min blending parameter
    let k = 0.3 - 0.2 * sin(t * 0.5);
    d = smin(d, dist, k);
    
    if (d < 0.001 || tVal > 12.0) {
      hit = true;
      break;
    }
    
    tVal += d;
  }
  
  var color = vec3f(0.01, 0.015, 0.025);
  
  if (hit) {
    let p = ro + rd * tVal;
    
    // Recompute normal with proper curl deformation
    let e = vec2f(0.001, 0.0);
    let nDeformed = normalize(vec3f(
      smin(d, sdSphere(p + vec3f(e.x, e.y, e.y), 0.0), 0.001) - smin(d, sdSphere(p - vec3f(e.x, e.y, e.y), 0.0), 0.001),
      smin(d, sdSphere(p + vec3f(e.y, e.x, e.y), 0.0), 0.001) - smin(d, sdSphere(p - vec3f(e.y, e.x, e.y), 0.0), 0.001),
      smin(d, sdSphere(p + vec3f(e.y, e.y, e.x), 0.0), 0.001) - smin(d, sdSphere(p - vec3f(e.y, e.y, e.x), 0.0), 0.001)
    ));
    
    let viewDir = normalize(ro - p);
    color = calcLighting(p, nDeformed, viewDir);
    
    // Add liquid sheen
    let sheen = pow(1.0 - max(dot(nDeformed, viewDir), 0.0), 5.0) * 0.3;
    color += vec3f(0.9, 0.95, 1.0) * sheen;
  }
  
  // Vignette
  let vig = 1.0 - length(uv - 0.5) * 0.8;
  color *= vig;
  
  // Ensure minimum brightness
  color = max(color, vec3f(0.03));
  
  return vec4f(color, 1.0);
}