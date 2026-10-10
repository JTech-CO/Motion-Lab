'use strict';

/* Motion Lab home controller.
 * CSS presentations derive from the three MIT Motion Lab recipes in home.css.
 * The Drop_Zone_Flicker source is read intact from its small catalog export. It runs
 * as GLSL with white/black input textures. Its output luminance becomes the
 * visibility mask of the live home DOM over the live library DOM.
 * This adaptation is a visibility transition, not a DOM texture RGB warp.
 * No imported JavaScript, iframe, DOM screenshot, or remote image is executed.
 */
(() => {
  const home = document.getElementById('home-view');
  const libraryView = document.getElementById('library-view');
  if (!home || !libraryView) return;
  const $ = (id) => document.getElementById(id);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const library = window.MotionLabLibrary;
  const state = { lang: document.documentElement.lang === 'en' ? 'en' : 'ko', paused: reduced.matches, entering: false, frame: 0, pipeline: null, source: null, stats: null, statsStatus: 'loading', statsFromCatalog: false, framesRendered: 0, generation: 0 };
  const copy = {
    ko: {
      title: 'Motion Lab', subtitle: '모션 코드, 디자인 에셋과 레퍼런스를 한곳에서.',
      motion: '모션', design: '디자인', references: '레퍼런스', total: '전체 자료', composition: '자료 구성',
      chart: '모션, 디자인, 레퍼런스 비율', statsLoading: '자료 구성을 불러오는 중입니다.', statsError: '자료 구성을 확인하지 못했습니다.',
      enter: '라이브러리 열기', pause: '모션 정지', play: '모션 재생', reduced: '시스템의 모션 줄이기 설정을 따릅니다.',
      entering: '라이브러리로 이동합니다.', fallback: '전환 효과를 생략하고 라이브러리로 이동합니다.'
    },
    en: {
      title: 'Motion Lab', subtitle: 'Motion code, design assets and references in one place.',
      motion: 'Motion', design: 'Design', references: 'References', total: 'Total entries', composition: 'Collection composition',
      chart: 'Motion, Design and References proportions', statsLoading: 'Loading collection composition.', statsError: 'Collection composition is unavailable.',
      enter: 'Explore the library', pause: 'Pause motion', play: 'Play motion', reduced: 'Respects the system reduced-motion setting.',
      entering: 'Opening the library.', fallback: 'Opening the library without the transition effect.'
    }
  };
  const t = (key) => copy[state.lang][key];
  const collections = ['motion', 'design', 'references'];
  function composition(stats) {
    if (!stats || typeof stats !== 'object') return null;
    const counts = [stats.domains?.motion, stats.domains?.design, stats.kinds?.reference];
    if (![...counts, stats.total, stats.storedAssets].every((value) => Number.isSafeInteger(value) && value >= 0 && value <= 1000000000)
      || counts.reduce((sum, value) => sum + value, 0) !== stats.total
      || counts[0] + counts[1] !== stats.storedAssets) return null;
    return { counts, total: stats.total };
  }
  function renderComposition() {
    const data = composition(state.stats);
    const format = new Intl.NumberFormat(state.lang === 'ko' ? 'ko-KR' : 'en-US');
    const percent = new Intl.NumberFormat(state.lang === 'ko' ? 'ko-KR' : 'en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const section = $('home-composition');
    section.setAttribute('aria-label', t('composition'));
    section.setAttribute('aria-busy', String(!data && state.statsStatus === 'loading'));
    section.dataset.ready = String(!!data);
    $('home-chart-title').textContent = t('chart');
    $('home-total-label').textContent = t('total');
    $('home-total').textContent = data ? format.format(data.total) : '...';
    const descriptions = [];
    let start = 0;
    collections.forEach((key, index) => {
      const count = data?.counts[index];
      const share = data && data.total ? count * 100 / data.total : 0;
      $('home-' + key + '-label').textContent = t(key);
      $('home-' + key + '-count').textContent = data ? format.format(count) : '...';
      $('home-' + key + '-share').textContent = data ? percent.format(share) + '%' : '';
      const segment = $('home-' + key + '-segment');
      segment.setAttribute('stroke-dasharray', share.toFixed(8) + ' 100');
      segment.setAttribute('stroke-dashoffset', (-start).toFixed(8));
      start += share;
      if (data) descriptions.push(t(key) + ': ' + format.format(count) + ' (' + percent.format(share) + '%)');
    });
    const status = state.statsStatus === 'loading' ? t('statsLoading') : t('statsError');
    $('home-chart-description').textContent = data ? descriptions.join('; ') : status;
    $('home-stats-status').textContent = data ? '' : status;
    $('home-stats-status').hidden = !!data;
  }
  function renderHome() {
    home.dataset.paused = String(state.paused || reduced.matches);
    $('home-subtitle').textContent = t('subtitle');
    renderComposition();
    $('home-enter-label').textContent = t('enter');
    $('home-pause').textContent = t(state.paused || reduced.matches ? 'play' : 'pause');
    $('home-pause').setAttribute('aria-pressed', String(state.paused || reduced.matches));
    $('home-pause').disabled = reduced.matches;
    $('home-pause').title = reduced.matches ? t('reduced') : t(state.paused ? 'play' : 'pause');
    $('home-language').textContent = state.lang === 'ko' ? 'KO / EN' : 'EN / KO';
    $('home-language').setAttribute('aria-label', state.lang === 'ko' ? 'Switch to English' : '한국어로 변경');
    $('home-github').setAttribute('aria-label', state.lang === 'ko' ? 'GitHub 저장소 새 탭에서 열기' : 'Open the GitHub repository in a new tab');
    $('home-note').textContent = reduced.matches ? t('reduced') : state.paused ? (state.lang === 'ko' ? '모션이 일시 정지되었습니다.' : 'Motion is paused.') : '';
    if (!home.hidden) {
      document.documentElement.lang = state.lang;
      document.title = t('title');
    }
  }
  function clearMask() {
    home.style.maskImage = '';
    home.style.webkitMaskImage = '';
  }
  function destroyPipeline() {
    const p = state.pipeline;
    state.pipeline = null;
    if (!p) return;
    try {
      p.gl.deleteTexture(p.from);
      p.gl.deleteTexture(p.to);
      p.gl.deleteBuffer(p.buffer);
      p.gl.deleteProgram(p.program);
      p.gl.getExtension('WEBGL_lose_context')?.loseContext();
    } catch (_) { /* Navigation remains available after context loss. */ }
    p.canvas.width = 1;
    p.canvas.height = 1;
    p.maskCanvas.width = 1;
    p.maskCanvas.height = 1;
  }
  function stopTransition() {
    cancelAnimationFrame(state.frame);
    state.frame = 0;
    state.generation++;
    state.entering = false;
    $('home-enter').removeAttribute('aria-disabled');
    destroyPipeline();
    clearMask();
  }
  function libraryRoute() { return location.hash === '#library' || location.hash === '#library-main'; }
  function libraryFocus() {
    const control = $('search-input') || libraryView.querySelector('button:not(:disabled)');
    if (control) control.focus({ preventScroll: true });
  }
  function showLibrary(pushHistory) {
    stopTransition();
    home.hidden = true;
    libraryView.hidden = false;
    libraryView.inert = false;
    document.body.dataset.view = 'library';
    if (library && typeof library.setActive === 'function') library.setActive(true);
    if (pushHistory && !libraryRoute()) history.pushState({ motionLabView: 'library' }, '', '#library');
    window.scrollTo(0, 0);
    libraryFocus();
  }
  function showHome(pushHistory) {
    stopTransition();
    libraryView.querySelectorAll('dialog[open]').forEach((dialog) => dialog.close());
    if (library && typeof library.setActive === 'function') library.setActive(false);
    libraryView.hidden = true;
    libraryView.inert = true;
    home.hidden = false;
    document.body.dataset.view = 'home';
    $('home-status').textContent = '';
    if (pushHistory && location.hash) history.pushState({ motionLabView: 'home' }, '', location.pathname + location.search);
    window.scrollTo(0, 0);
    renderHome();
    $('home-enter').focus({ preventScroll: true });
  }
  function compile(gl, type, source) {
    const shader = gl.createShader(type);
    if (!shader) throw new Error('Shader unavailable');
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { gl.deleteShader(shader); throw new Error('Shader compilation failed'); }
    return shader;
  }
  function makePipeline(item) {
    if (!item || item.id !== 'gl-transitions-drop-zone-flicker' || item.language !== 'glsl' || typeof item.code !== 'string' || item.code.length > 20000 || !/\bvec4\s+transition\s*\(\s*vec2\s+\w+\s*\)/.test(item.code)) return null;
    const canvas = document.createElement('canvas');
    const width = Math.min(320, Math.max(160, window.innerWidth));
    const height = Math.max(180, Math.min(480, Math.round(width * window.innerHeight / Math.max(1, window.innerWidth))));
    canvas.width = width;
    canvas.height = height;
    const gl = canvas.getContext('webgl', { alpha: false, antialias: false, preserveDrawingBuffer: true, depth: false, stencil: false });
    if (!gl) return null;
    let vertex = null, fragment = null, program = null, buffer = null, from = null, to = null;
    try {
      vertex = compile(gl, gl.VERTEX_SHADER, 'attribute vec2 position; varying vec2 uv; void main(){uv=(position+1.0)*0.5;gl_Position=vec4(position,0.0,1.0);}');
      const header = 'precision highp float;varying vec2 uv;uniform float progress;uniform float ratio;uniform sampler2D fromTexture;uniform sampler2D toTexture;vec4 getFromColor(vec2 p){return texture2D(fromTexture,p);}vec4 getToColor(vec2 p){return texture2D(toTexture,p);}\n';
      fragment = compile(gl, gl.FRAGMENT_SHADER, header + item.code + '\nvoid main(){gl_FragColor=transition(uv);}');
      program = gl.createProgram();
      if (!program) throw new Error('Program unavailable');
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      gl.deleteShader(vertex); vertex = null;
      gl.deleteShader(fragment); fragment = null;
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Shader linking failed');
      gl.useProgram(program);
      buffer = gl.createBuffer();
      if (!buffer) throw new Error('Buffer unavailable');
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
      const attribute = gl.getAttribLocation(program, 'position');
      gl.enableVertexAttribArray(attribute);
      gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0);
      function texture(unit, value) {
        const tex = gl.createTexture();
        if (!tex) throw new Error('Texture unavailable');
        gl.activeTexture(gl.TEXTURE0 + unit);
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([value,value,value,255]));
        return tex;
      }
      from = texture(0, 255);
      to = texture(1, 0);
      gl.uniform1i(gl.getUniformLocation(program, 'fromTexture'), 0);
      gl.uniform1i(gl.getUniformLocation(program, 'toTexture'), 1);
      gl.uniform1f(gl.getUniformLocation(program, 'ratio'), window.innerWidth / Math.max(1, window.innerHeight));
      const defaults = { frameRate: 24, rgbOffset: 0.014, blockAmount: 0.72, ghostAmount: 0.62, redCyan: 0.58, scanline: 0.075 };
      Object.entries(defaults).forEach(([name,value]) => gl.uniform1f(gl.getUniformLocation(program,name),value));
      const maskCanvas = document.createElement('canvas');
      maskCanvas.width = width;
      maskCanvas.height = height;
      const ctx = maskCanvas.getContext('2d');
      if (!ctx) throw new Error('Mask canvas unavailable');
      const p = { gl, canvas, program, buffer, from, to, width, height, maskCanvas, ctx, pixels: new Uint8Array(width * height * 4), mask: ctx.createImageData(width,height), progress: gl.getUniformLocation(program,'progress') };
      canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        if (state.pipeline === p && state.entering) showLibrary(true);
      });
      gl.viewport(0,0,width,height);
      return p;
    } catch (_) {
      if (vertex) gl.deleteShader(vertex);
      if (fragment) gl.deleteShader(fragment);
      if (from) gl.deleteTexture(from);
      if (to) gl.deleteTexture(to);
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      return null;
    }
  }
  function drawMask(progress) {
    const p = state.pipeline;
    if (!p) throw new Error('Mask unavailable');
    p.gl.useProgram(p.program);
    p.gl.uniform1f(p.progress, progress);
    p.gl.drawArrays(p.gl.TRIANGLES,0,6);
    p.gl.readPixels(0,0,p.width,p.height,p.gl.RGBA,p.gl.UNSIGNED_BYTE,p.pixels);
    if (p.gl.getError() !== p.gl.NO_ERROR) throw new Error('Mask render failed');
    const target = p.mask.data;
    for (let y=0;y<p.height;y++) for (let x=0;x<p.width;x++) {
      const source=((p.height-1-y)*p.width+x)*4;
      const dest=(y*p.width+x)*4;
      target[dest]=255;target[dest+1]=255;target[dest+2]=255;
      target[dest+3]=Math.round((p.pixels[source]*0.2126+p.pixels[source+1]*0.7152+p.pixels[source+2]*0.0722)*p.pixels[source+3]/255);
    }
    p.ctx.putImageData(p.mask,0,0);
    const image='url("' + p.maskCanvas.toDataURL('image/png') + '")';
    home.style.maskImage=image;
    home.style.webkitMaskImage=image;
    state.framesRendered++;
    home.dataset.transitionFrames=String(state.framesRendered);
  }
  const ready = library && library.ready && typeof library.ready.then === 'function' ? library.ready : Promise.resolve(null);
  function acceptCatalog(data) {
    if (composition(data?.stats)) {
      state.stats = data.stats;
      state.statsStatus = 'ready';
      state.statsFromCatalog = true;
    }
    renderHome();
  }
  ready.then(acceptCatalog).catch(() => {});
  document.addEventListener('motionlab:catalog-ready',(event)=>acceptCatalog(event.detail));
  async function loadComposition() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch('./catalog-stats.json', { signal: controller.signal });
      if (!response.ok) throw new Error('Composition unavailable');
      const text = await response.text();
      if (text.length > 65536) throw new Error('Composition too large');
      const payload = JSON.parse(text);
      const stats = payload?.stats;
      if (!composition(stats)) throw new Error('Invalid composition');
      if (!state.statsFromCatalog) { state.stats = stats; state.statsStatus = 'ready'; }
    } catch (_) {
      if (!state.stats) state.statsStatus = 'error';
    } finally {
      clearTimeout(timeout);
      renderComposition();
    }
  }
  loadComposition();
  async function loadTransition() {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch('./home-transition.json', { signal: controller.signal });
      if (!response.ok) throw new Error('Transition unavailable');
      const text = await response.text();
      if (text.length > 65536) throw new Error('Transition too large');
      const payload = JSON.parse(text), item = payload?.item;
      if (payload?.version !== 1 || !item || item.id !== 'gl-transitions-drop-zone-flicker'
        || item.language !== 'glsl' || typeof item.code !== 'string' || item.code.length > 20000) throw new Error('Invalid transition');
      state.source = item;
    } catch (_) { state.source = null; }
    finally {
      clearTimeout(timeout);
      home.dataset.transitionSource = state.source ? state.source.id : 'unavailable';
    }
  }
  const sourceReady = loadTransition();
  async function enterLibrary(event) {
    event.preventDefault();
    if (state.entering) return;
    if (!library || typeof library.setActive !== 'function') { location.assign('./library.html'); return; }
    state.entering=true;
    const generation=++state.generation;
    $('home-enter').setAttribute('aria-disabled','true');
    $('home-status').textContent=t('entering');
    library.setActive(true);
    await sourceReady;
    if (generation!==state.generation || home.hidden) return;
    libraryView.hidden=false;
    libraryView.inert=true;
    if (state.paused || reduced.matches || !state.source) { home.dataset.transition='skipped';showLibrary(true);return; }
    state.pipeline=makePipeline(state.source);
    if (!state.pipeline) { home.dataset.transition='unavailable';$('home-status').textContent=t('fallback');showLibrary(true);return; }
    state.framesRendered=0;
    home.dataset.transition='glsl-visibility-mask';
    home.dataset.transitionSource=state.source.id;
    let start=null,lastFrame=-1;
    function tick(time) {
      if (generation!==state.generation || !state.entering) return;
      if (start===null) start=time;
      const progress=Math.min(1,(time-start)/1000),frame=Math.floor(progress*24);
      try { if (frame!==lastFrame) { drawMask(progress);lastFrame=frame; } }
      catch (_) { home.dataset.transition='unavailable';showLibrary(true);return; }
      if (progress>=1) showLibrary(true);
      else state.frame=requestAnimationFrame(tick);
    }
    state.frame=requestAnimationFrame(tick);
  }
  $('home-enter').addEventListener('click',enterLibrary);
  $('home-pause').addEventListener('click',() => {
    state.paused=reduced.matches||!state.paused;
    renderHome();
    if (library && typeof library.setPaused==='function') library.setPaused(state.paused);
    if (state.entering) showLibrary(true);
  });
  $('home-language').addEventListener('click',() => {
    state.lang=state.lang==='ko'?'en':'ko';
    if (library && typeof library.setLanguage==='function') library.setLanguage(state.lang);
    renderHome();
  });
  function syncLanguage(event) {
    const lang=event.detail && event.detail.lang;
    if (!['ko','en'].includes(lang) || lang===state.lang) return;
    state.lang=lang;
    renderHome();
  }
  function syncPause(event) {
    const paused=event.detail && event.detail.paused;
    if (typeof paused!=='boolean') return;
    state.paused=paused||reduced.matches;
    renderHome();
  }
  window.addEventListener('motionlab:language',syncLanguage);
  document.addEventListener('motionlab:language',syncLanguage);
  window.addEventListener('motionlab:pause',syncPause);
  document.addEventListener('motionlab:pause',syncPause);
  reduced.addEventListener('change',()=> {
    if (reduced.matches) {
      state.paused=true;
      if (library && typeof library.setPaused==='function') library.setPaused(true);
      if (state.entering) showLibrary(true);
    }
    renderHome();
  });
  document.addEventListener('keydown',(event)=> {
    if (home.hidden || event.ctrlKey || event.metaKey || event.altKey) return;
    const controls=[$('home-enter'),$('home-pause'),$('home-github'),$('home-language')].filter((el)=>!el.disabled);
    if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) {
      event.preventDefault();event.stopImmediatePropagation();
      const index=controls.indexOf(document.activeElement),forward=['ArrowDown','ArrowRight'].includes(event.key),next=index<0?0:(index+(forward?1:-1)+controls.length)%controls.length;
      controls[next].focus();
    } else if (event.key==='Enter') {
      event.stopImmediatePropagation();
      if (!controls.includes(document.activeElement)) { event.preventDefault();$('home-enter').focus();$('home-enter').click(); }
    }
  },true);
  libraryView.querySelector('.brand')?.addEventListener('click',(event)=> { event.preventDefault();showHome(true); });
  function applyRoute() {
    if (libraryRoute()) {
      if (!home.hidden) showLibrary(false);
    } else if (!location.hash || location.hash==='#home') showHome(false);
  }
  window.addEventListener('popstate',applyRoute);
  window.addEventListener('hashchange',applyRoute);
  window.addEventListener('pagehide',stopTransition);
  window.addEventListener('pageshow',(event)=> { if (event.persisted) applyRoute(); });
  renderHome();
  if (libraryRoute()) showLibrary(false);
  else showHome(false);
})();

