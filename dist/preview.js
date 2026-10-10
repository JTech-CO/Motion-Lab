'use strict';

/* Trusted preview host. Imported HTML/JavaScript is never executed. */
(() => {
  const instances = new Set();
  const cssCache = new Map();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let serial = 0;
  const labels = {
    ko: { css: '원본 CSS · 동작 샘플', composition: '원본 CSS · 구성 요소 재생', glsl: '원본 GLSL · 테스트 장면 A → B', procedural: '원본 GLSL · 기본값으로 재생하는 절차형 효과', svg: '원본 SVG 애니메이션', palette: '실제 색상 값', gradient: '실제 그라디언트', reference: '원본 검토 필요', noPreview: '수록된 시각 에셋이 없습니다.', invalid: '안전하게 재생할 수 없는 형식입니다.', webgl: '이 환경에서는 WebGL 미리보기를 사용할 수 없습니다.', shader: '이 셰이더는 현재 호스트에서 컴파일되지 않습니다.' },
    en: { css: 'Original CSS · motion sample', composition: 'Original CSS · component playback', glsl: 'Original GLSL · test scenes A → B', procedural: 'Original GLSL · procedural effect at source defaults', svg: 'Original SVG animation', palette: 'Actual color values', gradient: 'Actual gradient', reference: 'Original review required', noPreview: 'No visual asset is stored in this record.', invalid: 'This format cannot be previewed safely.', webgl: 'WebGL preview is unavailable in this environment.', shader: 'This shader does not compile in the current host.' }
  };
  const element = (tag, className, text) => { const e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e; };
  const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const colorsOf = item => Array.isArray(item.colors) ? item.colors.filter(c => typeof c === 'string' && /^#(?:[a-f0-9]{6}|[a-f0-9]{8})$/i.test(c)).slice(0, 32) : [];
  function paletteTextColor(color) {
    const [r,g,b,a=255] = color.slice(1).match(/../g).map(value => parseInt(value,16));
    const alpha = a / 255, backdrop = 8*.299 + 11*.587 + 13*.114;
    return (r*.299+g*.587+b*.114)*alpha+backdrop*(1-alpha)>145 ? '#061215' : '#f7ffff';
  }
  const stripComments = value => value.replace(/\/\*[\s\S]*?\*\//g, '');
  function stripCssComments(source) {
    let result = '', quote = '';
    for (let i = 0; i < source.length; i++) {
      const character = source[i];
      if (quote) {
        result += character;
        if (character === '\\' && i + 1 < source.length) result += source[++i];
        else if (character === quote) quote = '';
      } else if (character === '"' || character === "'") { quote = character; result += character; }
      else if (character === '/' && source[i + 1] === '*') {
        const end = source.indexOf('*/', i + 2);
        if (end < 0) return '';
        i = end + 1;
      } else result += character;
    }
    return quote ? '' : result;
  }
  // Read bounded CSS syntax, preserving authored declarations before CSSOM
  // expands shorthands. A later longhand override can make every CSSOM spelling
  // of a var()-containing shorthand empty, including its serialized cssText.
  // Strings, comments and function arguments are never treated as declarations.
  function sourceRules(source) {
    const rules = [], stack = [];
    let quote = '', depth = 0, start = 0, opening = -1, prelude = '';
    for (let i = 0; i < source.length; i++) {
      const character = source[i];
      if (quote) { if (character === quote) quote = ''; continue; }
      if (character === '"' || character === "'") { quote = character; continue; }
      if (character === '(' || character === '[') { if (stack.length >= 48) return null; stack.push(character); continue; }
      if (character === ')' || character === ']') { if (stack.pop() !== (character === ')' ? '(' : '[')) return null; continue; }
      if (stack.length) continue;
      if (character === '{') {
        if (depth === 0) { prelude = source.slice(start, i).trim(); opening = i; }
        if (++depth > 32) return null;
      } else if (character === '}') {
        if (!depth) return null;
        if (--depth === 0) { rules.push({ prelude, body: source.slice(opening + 1, i) }); start = i + 1; }
      } else if (character === ';' && depth === 0) { rules.push({ prelude: source.slice(start, i).trim(), body: null }); start = i + 1; }
    }
    if (quote || depth || stack.length) return null;
    if (source.slice(start).trim()) rules.push({ prelude: source.slice(start).trim(), body: null });
    return rules;
  }
  function sourceDeclarations(source) {
    const entries = [], stack = [];
    let quote = '', start = 0;
    for (let i = 0; i <= source.length; i++) {
      const character = source[i];
      if (quote) { if (character === quote) quote = ''; continue; }
      if (character === '"' || character === "'") { quote = character; continue; }
      if (character === '(' || character === '[') { if (stack.length >= 48) return null; stack.push(character); continue; }
      if (character === ')' || character === ']') { if (stack.pop() !== (character === ')' ? '(' : '[')) return null; continue; }
      if (character === '{' || character === '}') return null;
      if ((character === ';' || i === source.length) && !stack.length) { entries.push(source.slice(start, i)); start = i + 1; }
    }
    return quote || stack.length ? null : entries;
  }
  const properties = new Set(('animation animation-name animation-duration animation-delay animation-timing-function animation-iteration-count animation-direction animation-fill-mode animation-play-state transform transform-origin transform-style perspective backface-visibility opacity visibility filter box-shadow text-shadow background background-color background-image background-size background-position background-repeat background-clip color border border-width border-style border-color border-radius border-bottom-right-radius border-top border-right border-bottom border-left border-top-color border-right-color border-bottom-color border-left-color width height min-width min-height max-width max-height margin margin-top margin-right margin-bottom margin-left padding padding-top padding-right padding-bottom padding-left position top right bottom left inset display flex flex-direction flex-wrap align-items justify-content place-items gap overflow box-sizing font font-size font-family font-weight font-variant-numeric letter-spacing line-height text-align text-indent text-transform white-space content clip-path isolation transition transition-property transition-duration transition-timing-function transition-delay pointer-events cursor vertical-align float clear grid grid-template-columns grid-template-rows grid-auto-flow grid-auto-columns grid-auto-rows grid-column grid-row grid-column-start grid-column-end grid-row-start grid-row-end justify-items align-content place-content row-gap column-gap aspect-ratio background-origin background-blend-mode mix-blend-mode mask mask-image mask-size mask-position mask-repeat mask-composite mask-mode scale rotate translate perspective-origin will-change text-fill-color text-stroke appearance outline outline-width outline-style outline-color outline-offset offset-path offset-distance offset-rotate backdrop-filter z-index').split(' '));
  function declarations(source) {
    const output = [], entries = sourceDeclarations(source);
    if (!entries) return '';
    const style = document.createElement('div').style;
    for (const entry of entries) {
      const colon = entry.indexOf(':');
      if (colon < 1) continue;
      const authoredProperty = entry.slice(0, colon).trim();
      const property = authoredProperty.startsWith('--') ? authoredProperty : authoredProperty.toLowerCase();
      if (!/^(?:-webkit-)?[a-z][a-z0-9-]*$/.test(property) && !/^--[a-z_][a-z0-9_-]{0,70}$/i.test(property)) continue;
      const plain = property.replace(/^-webkit-/, '');
      let value = entry.slice(colon + 1).trim();
      const important = /!\s*important\s*$/i.test(value);
      if (important) value = value.replace(/!\s*important\s*$/i, '').trim();
      if (!value) continue;
      if (!properties.has(plain) && !/^--[a-z_][a-z0-9_-]{0,70}$/i.test(property)) continue;
      if (value.length > 2400 || /[\\<>]|(?:url|expression|image-set|attr)\s*\(/i.test(value)) continue;
      if (plain === 'content' && !/^(?:none|normal|"[^"\\]{0,80}"|'[^'\\]{0,80}')$/.test(value.trim())) continue;
      // Validate each complete declaration with CSSOM independently, preserving
      // its original value and cascade order only after the browser accepts it.
      style.cssText = '';
      style.setProperty(property, value, important ? 'important' : '');
      // Valid shorthands such as border-bottom:none can also serialize as an
      // empty shorthand. Accepted expanded longhands still prove CSSOM parsed
      // the declaration; an invalid declaration leaves this empty style empty.
      if (!style.length) continue;
      output.push(`${property}:${value}${important ? '!important' : ''};`);
    }
    return output.join('');
  }
  function safeVariables(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return '';
    const output = [];
    for (const [name, value] of Object.entries(raw).slice(0, 32)) {
      if (!/^--[a-z_][a-z0-9_-]{0,70}$/i.test(name) || typeof value !== 'string' || value.length > 240) continue;
      if (!/^[a-z0-9#().,%\s_+-]+$/i.test(value) || /(?:url|expression|image-set|attr)\s*\(/i.test(value)) continue;
      output.push(`${name}:${value};`);
    }
    return output.join('');
  }
  function safeTree(raw, budget = { count: 0 }, depth = 0) {
    if (!raw || typeof raw !== 'object' || depth > 5 || ++budget.count > 64) return null;
    const tag = ['div', 'span', 'p', 'strong', 'em', 'h1', 'h2', 'button', 'input', 'label'].includes(raw.tag) ? raw.tag : 'div';
    const className = typeof raw.className === 'string' && /^[a-z0-9_ -]{0,180}$/i.test(raw.className) ? raw.className.trim() : '';
    const text = typeof raw.text === 'string' ? raw.text.slice(0, 80) : '';
    const placeholder = typeof raw.placeholder === 'string' ? raw.placeholder.slice(0, 80) : '';
    const variables = safeVariables(raw.variables);
    const children = tag === 'input' ? [] : Array.isArray(raw.children) ? raw.children.slice(0, 32).map(c => safeTree(c, budget, depth + 1)).filter(Boolean) : [];
    return { tag, className, text, placeholder, variables, children };
  }
  function treeHtml(tree) {
    const attributes = `${tree.className ? ` class="${escape(tree.className)}"` : ''}${tree.variables ? ` style="${escape(tree.variables)}"` : ''}`;
    if (tree.tag === 'input') return `<input${attributes} type="text" readonly tabindex="-1" placeholder="${escape(tree.placeholder)}">`;
    const button = tree.tag === 'button' ? ' type="button" tabindex="-1"' : '';
    return `<${tree.tag}${attributes}${button}>${escape(tree.text)}${tree.children.map(treeHtml).join('')}</${tree.tag}>`;
  }
  function treeClasses(tree, classes = new Set(['motion-sample'])) { for (const c of tree.className.split(' ')) if (c) classes.add(c); tree.children.forEach(child => treeClasses(child, classes)); return classes; }
  function sanitizedCss(item, tree) {
    const source = typeof item.code === 'string' ? stripCssComments(item.code) : '';
    if (!source || source.length > 180000 || /[\\<]|(?:url|expression|image-set|attr)\s*\(|@(?:import|font-face|namespace|document|supports|layer|property)/i.test(source)) return '';
    const classes = tree ? treeClasses(tree) : new Set(['motion-sample']);
    const key = item.id + ':' + source.length + ':' + [...classes].join(',');
    if (cssCache.has(key)) return cssCache.get(key);
    const blocks = [];
    let found = false;
    function selectorAllowed(selector) {
      if (selector.length > 280 || !/^[a-z0-9_.:#() +>~,*-]+$/i.test(selector)) return false;
      if (!/^\.[a-z][a-z0-9_-]*/i.test(selector)) return false;
      if ([...selector.matchAll(/\.([a-z0-9_-]+)/gi)].some(m => !classes.has(m[1]))) return false;
      if (/\b(?:html|body|iframe|script|style|form)\b/i.test(selector) || selector.includes('#')) return false;
      const remainder = selector.replace(/\.[a-z0-9_-]+/gi, '').replace(/::?(?:before|after|placeholder|hover|active|focus-within|focus-visible|focus|first-child|last-child|nth-child\([0-9n+ -]+\)|nth-of-type\([0-9n+ -]+\))/gi, '').replace(/\b(?:div|span|p|strong|em|h1|h2|button|input|label)\b/g, '');
      return /^[\s>+~*]*$/.test(remainder);
    }
    try {
      const sheet = new CSSStyleSheet(); sheet.replaceSync(source);
      const originals = sourceRules(source);
      if (!originals || sheet.cssRules.length > 200 || originals.length > 200) return '';
      function accept(original, depth = 0) {
        if (original.body === null) return;
        const parsed = new CSSStyleSheet(); parsed.replaceSync(`${original.prelude}{${original.body}}`);
        if (parsed.cssRules.length !== 1) return;
        const rule = parsed.cssRules[0];
        if (rule.type === CSSRule.KEYFRAMES_RULE && /^[a-z0-9_-]{1,100}$/i.test(rule.name) && rule.cssRules.length <= 240) {
          const originalFrames = sourceRules(original.body);
          if (!originalFrames || originalFrames.length > 240) return;
          const frames = [];
          for (const originalFrame of originalFrames) {
            if (originalFrame.body === null) continue;
            const frameSheet = new CSSStyleSheet(); frameSheet.replaceSync(`@keyframes ${rule.name}{${originalFrame.prelude}{${originalFrame.body}}}`);
            const parsedFrames = frameSheet.cssRules[0]?.cssRules;
            if (parsedFrames?.length !== 1) continue;
            const frame = parsedFrames[0];
            if (/^(?:(?:from|to|\d+(?:\.\d+)?%)\s*,?\s*)+$/i.test(frame.keyText)) frames.push(`${frame.keyText}{${declarations(originalFrame.body)}}`);
          }
          if (frames.length) blocks.push(`@keyframes ${rule.name}{${frames.join('')}}`);
        } else if (rule.type === CSSRule.STYLE_RULE) {
          const selectors = rule.selectorText.split(',').map(s => s.trim());
          if (selectors.length <= 12 && selectors.every(selectorAllowed)) { blocks.push(`${selectors.join(',')}{${declarations(original.body)}}`); found = true; }
        } else if (depth < 2 && rule.type === CSSRule.MEDIA_RULE && /^\(prefers-reduced-motion:\s*reduce\)$/.test(rule.conditionText)) {
          const nestedOriginals = sourceRules(original.body);
          if (!nestedOriginals || nestedOriginals.length > 200) return;
          const initial = blocks.length; for (const nested of nestedOriginals) accept(nested, depth + 1);
          const nested = blocks.splice(initial); if (nested.length) blocks.push(`@media(prefers-reduced-motion:reduce){${nested.join('')}}`);
        }
      }
      for (const rule of originals) accept(rule);
    } catch { return ''; }
    const result = found ? blocks.join('\n') : '';
    cssCache.set(key, result); if (cssCache.size > 800) cssCache.delete(cssCache.keys().next().value);
    return result;
  }
  function cssDocument(item, paused, interaction) {
    // Only supplied component DOM is a composition. Analysis may infer a bare
    // .motion-sample node; standalone keyframes still need a visible target.
    const tree = safeTree(item.preview?.dom);
    const clean = sanitizedCss(item, tree); if (!clean) return null;
    const kind = item.analysis?.assetType || item.category;
    let markup;
    let sampleStyle;
    if (tree) { markup = treeHtml(tree); sampleStyle = ''; }
    else {
      const sampleText = typeof item.preview?.sampleText === 'string' ? item.preview.sampleText.slice(0, 70) : '';
      const actualSample = Boolean(sampleText);
      if (kind === 'typography' || item.analysis?.components?.includes('text')) {
        markup = `<div class="motion-sample">${escape(sampleText || 'Motion.')}</div>`;
        sampleStyle = '.motion-sample{font:600 34px/1.15 system-ui,sans-serif;letter-spacing:-1px;color:#d9f6f7;max-width:90%;text-align:center}';
      } else if (kind === 'transition' || item.language === 'glsl') {
        markup = '<div class="scene-under"><span>B</span></div><div class="motion-sample"><div class="scene-orb"></div><strong>A</strong><span class="scene-lines"></span></div>';
        sampleStyle = '.scene-under,.motion-sample{position:absolute;width:150px;height:96px;left:50%;top:50%;margin:-48px 0 0 -75px;border-radius:6px;overflow:hidden;border:1px solid #3b686c;background:#102e34}.scene-under{background:#d4e8e7;border-color:#d4e8e7;color:#08232a;display:flex;align-items:center;justify-content:center;font:600 45px/1 system-ui}.motion-sample{background:#0a1d25;color:#e8f7f7;perspective:500px}.motion-sample strong{position:absolute;left:18px;bottom:18px;font:600 27px/1 system-ui}.scene-orb{position:absolute;right:-15px;top:-15px;width:88px;height:88px;border-radius:50%;background:#6ee7f2}.scene-lines{position:absolute;left:20px;top:20px;width:35px;height:4px;background:#d6ebeb;box-shadow:0 8px #d6ebeb}';
      } else if (kind === 'loader') {
        markup = '<div class="motion-sample"></div>';
        sampleStyle = '.motion-sample{width:16px;height:16px;border-radius:50%;background:#6ee7f2;color:#6ee7f2}';
      } else if (kind === 'interaction') {
        markup = `<div class="motion-sample">${escape(sampleText || 'Hover / press')}</div>`;
        sampleStyle = '.motion-sample{padding:14px 22px;border-radius:7px;background:#162d32;border:1px solid #6ee7f2;color:#dbf7f9;font:500 16px/1.5 system-ui}';
      } else if (actualSample) {
        markup = `<div class="motion-sample">${escape(sampleText)}</div>`;
        sampleStyle = '.motion-sample{font:600 28px/1 system-ui;color:#6ee7f2}';
      } else {
        markup = '<div class="motion-sample"><span class="orb-center"></span></div>';
        sampleStyle = '.motion-sample{width:54px;height:54px;border-radius:50%;background:#6ee7f2;box-shadow:0 0 0 10px #6ee7f216;display:grid;place-items:center;color:#061719}.orb-center{width:14px;height:14px;border:2px solid #0b2228;border-radius:50%}';
      }
    }
    const extra = paused || reduced.matches ? '*,*::before,*::after{animation-play-state:paused!important}.motion-sample{animation-delay:-.9s!important}' : '';
    const hover = interaction ? clean.replace(/:(?:hover|active|focus-within|focus-visible|focus)(?![a-z-])/g, '.preview-active') : clean;
    if (interaction) markup = markup.replace(/class="([^"]+)"/g, (_, classes) => `class="${classes} preview-active"`);
    const rootVariables = safeVariables(item.preview?.variables);
    const base = `:root{${rootVariables}}` + 'html,body{width:100%;height:100%;margin:0;background:#080b0d;color:#6ee7f2;overflow:hidden}body{display:flex;align-items:center;justify-content:center;font-family:system-ui,sans-serif;position:relative}*{box-sizing:border-box}';
    return { document: `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><style>${base}${sampleStyle}${hover}${extra}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-play-state:paused!important}}</style></head><body>${markup}</body></html>`, composition: Boolean(tree) };
  }

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const svgTags = new Set(['svg','title','g','symbol','path','circle','ellipse','rect','line','polyline','polygon','defs','pattern','linearGradient','radialGradient','stop','clipPath','mask','use','animate','animateTransform','set','filter','feGaussianBlur','feColorMatrix','feBlend','feFlood','feOffset','feComposite','feMorphology']);
  const svgAttributes = new Set(['viewBox','width','height','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','d','points','fill','fill-opacity','fill-rule','stroke','stroke-width','stroke-opacity','stroke-linecap','stroke-linejoin','stroke-miterlimit','overflow','stroke-dasharray','stroke-dashoffset','opacity','transform','transform-origin','transform-box','style','gradientTransform','gradientUnits','patternUnits','patternContentUnits','patternTransform','offset','stop-color','stop-opacity','id','clip-path','mask','filter','href','preserveAspectRatio','attributeName','attributeType','type','from','to','by','values','dur','begin','repeatCount','keyTimes','keySplines','calcMode','additive','accumulate','in','in2','result','mode','stdDeviation','filterUnits','primitiveUnits','color-interpolation-filters','flood-color','flood-opacity','dx','dy','operator','k1','k2','k3','k4','radius']);
  const animationNames = new Set(['transform','opacity','fill','fill-opacity','stroke','stroke-opacity','stroke-width','stroke-dashoffset','stroke-dasharray','r','rx','ry','cx','cy','x','y','width','height','d','points']);
  const svgEnums = {
    'clip-rule': new Set(['nonzero','evenodd']),
    maskUnits: new Set(['userSpaceOnUse','objectBoundingBox']),
    maskContentUnits: new Set(['userSpaceOnUse','objectBoundingBox']),
    'mask-type': new Set(['alpha','luminance']),
    'shape-rendering': new Set(['auto','optimizeSpeed','crispEdges','geometricPrecision']),
    'mix-blend-mode': new Set(['normal','multiply','screen','overlay','darken','lighten','color-dodge','color-burn','hard-light','soft-light','difference','exclusion','hue','saturation','color','luminosity'])
  };
  for (const name of Object.keys(svgEnums)) svgAttributes.add(name);
  function safeSvgStyle(name, value) {
    if (typeof value !== 'string' || value.length > 160) return '';
    value = value.trim();
    if (svgEnums[name]) return svgEnums[name].has(value) ? value : '';
    if (name === 'transform-box') return /^(?:fill-box|stroke-box|view-box|border-box|content-box)$/.test(value) ? value : '';
    if (name === 'transform-origin') {
      const token = '(?:left|right|top|bottom|center|-?(?:[0-9]+(?:\\.[0-9]+)?|\\.[0-9]+)(?:px|%|em|rem)?)';
      return new RegExp(`^${token}(?:\\s+${token}){0,2}$`).test(value) ? value : '';
    }
    return '';
  }
  function sanitizedSvg(code) {
    if (typeof code !== 'string' || code.length > 160000 || /<!DOCTYPE|<!ENTITY/i.test(code)) return null;
    const source = new DOMParser().parseFromString(code, 'image/svg+xml');
    if (source.querySelector('parsererror') || source.documentElement.localName !== 'svg') return null;
    let count = 0, filterCount = 0;
    const idPrefix = 'ml-svg-' + (++serial) + '-';
    const localIds = new Set([...source.querySelectorAll('[id]')].slice(0,700)
      .filter(node=>svgTags.has(node.localName)&&/^[a-z0-9_-]{1,100}$/i.test(node.id)).map(node=>node.id));
    function safeBegin(value) {
      if(value.length>1000)return '';
      const parts=value.split(';').map(part=>part.trim()).filter(Boolean);
      if(!parts.length||parts.length>8)return '';
      const clock=/^([+-]?(?:\d+(?:\.\d+)?|\.\d+))(ms|s)$/;
      const boundedClock=part=>{const match=clock.exec(part);return Boolean(match&&Math.abs(Number(match[1]))/(match[2]==='ms'?1000:1)<=3600);};
      const clean=[];
      for(const part of parts){
        if(boundedClock(part)){clean.push(part);continue;}
        const sync=/^([a-z0-9_-]{1,100})\.(begin|end)([+-](?:\d+(?:\.\d+)?|\.\d+)(?:ms|s))?$/i.exec(part);
        if(!sync||!localIds.has(sync[1])||(sync[3]&&!boundedClock(sync[3])))return '';
        clean.push(idPrefix+sync[1]+'.'+sync[2]+(sync[3]||''));
      }
      return clean.join(';');
    }
    const boundedNumber = (value, limit, positive = false) => /^-?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:e[+-]?[0-9]+)?$/i.test(value) && Number.isFinite(Number(value)) && Math.abs(Number(value)) <= limit && (!positive || Number(value) >= 0);
    function copy(node, depth = 0) {
      if (depth > 12 || ++count > 700 || !svgTags.has(node.localName)) return null;
      if (node.localName === 'filter' && ++filterCount > 8) return null;
      const out = document.createElementNS(SVG_NS, node.localName);
      if(node.localName==='title')out.textContent=(node.textContent||'').slice(0,300);
      for (const attribute of node.attributes) {
        const name = attribute.name === 'xlink:href' ? 'href' : attribute.name;
        let value = attribute.value;
        if (!svgAttributes.has(name) || value.length > 22000) continue;
        if (name === 'style') {
          if (value.length > 320) continue;
          for (const declaration of value.split(';').slice(0, 8)) {
            const colon = declaration.indexOf(':');
            if (colon < 0) continue;
            const property = declaration.slice(0, colon).trim();
            const clean = safeSvgStyle(property, declaration.slice(colon + 1));
            if (clean) out.style.setProperty(property, clean);
          }
          continue;
        }
        if (/[<>\\]|javascript:|data:|https?:/i.test(value)) continue;
        if (name === 'id') { if (!/^[a-z0-9_-]{1,100}$/i.test(value)) continue; value = idPrefix + value; }
        else if (name === 'href') { if (!/^#[a-z0-9_-]{1,100}$/i.test(value)) continue; value = '#' + idPrefix + value.slice(1); }
        else if (['mask','clip-path','filter'].includes(name) || /^url\(/i.test(value)) { const m = /^url\(\s*(['"]?)#([a-z0-9_-]{1,100})\1\s*\)$/i.exec(value); if (!m) continue; value = `url(#${idPrefix}${m[2]})`; }
        else if (svgEnums[name] || name === 'transform-origin' || name === 'transform-box') { value = safeSvgStyle(name, value); if (!value) continue; }
        else if (name === 'stdDeviation') {
          const numbers = value.trim().split(/[,\s]+/);
          if (node.localName !== 'feGaussianBlur' || numbers.length < 1 || numbers.length > 2 || numbers.some(n => !/^(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$/.test(n) || !Number.isFinite(Number(n)) || Number(n) > 40)) return null;
        }
        else if (['in','in2','result'].includes(name)) { if (!/^[a-z_][a-z0-9_-]{0,99}$/i.test(value)) continue; }
        else if (name === 'filterUnits' || name === 'primitiveUnits') { if (node.localName !== 'filter' || !/^(?:userSpaceOnUse|objectBoundingBox)$/.test(value)) continue; }
        else if (name === 'color-interpolation-filters') { if (node.localName !== 'filter' || !/^(?:sRGB|linearRGB)$/.test(value)) continue; }
        else if (name === 'flood-color') { if (node.localName !== 'feFlood' || value.length > 80 || /url\(/i.test(value) || !CSS.supports('color', value)) continue; }
        else if (name === 'flood-opacity') { if (node.localName !== 'feFlood' || !boundedNumber(value, 1, true)) return null; }
        else if (name === 'dx' || name === 'dy') { if (node.localName !== 'feOffset' || !boundedNumber(value, 256)) return null; }
        else if (/^k[1-4]$/.test(name)) { if (node.localName !== 'feComposite' || !boundedNumber(value, 16)) return null; }
        else if (name === 'radius') {
          const numbers = value.trim().split(/[,\s]+/);
          if (node.localName !== 'feMorphology' || numbers.length < 1 || numbers.length > 2 || numbers.some(n => !boundedNumber(n, 40, true))) return null;
        }
        else if (name === 'operator') {
          if (node.localName === 'feMorphology' ? !/^(?:erode|dilate)$/.test(value) : node.localName !== 'feComposite' || !/^(?:over|in|out|atop|xor|arithmetic)$/.test(value)) return null;
        }
        else if (name === 'mode') {
          if (node.localName === 'feColorMatrix' ? value !== 'matrix' : node.localName !== 'feBlend' || !/^(?:normal|multiply|screen|darken|lighten|overlay)$/.test(value)) continue;
        }
        else if (name === 'values' && node.localName === 'feColorMatrix') {
          const numbers = value.trim().split(/[,\s]+/);
          if (numbers.length !== 20 || numbers.some(n => !boundedNumber(n, 256))) continue;
        }
        else if (name === 'attributeName' && !animationNames.has(value)) continue;
        else if (name === 'begin') {value=safeBegin(value);if(!value)continue;}
        else if (!/^[a-z0-9#.,;()%+\s:_-]*$/i.test(value)) continue;
        out.setAttribute(name, value);
      }
      if (['animate','animateTransform','set'].includes(node.localName) && !animationNames.has(out.getAttribute('attributeName'))) return null;
      for (const child of node.children) { const copied = copy(child, depth + 1); if (copied) out.append(copied); }
      return out;
    }
    const result = copy(source.documentElement);
    if (result) { result.classList.add('motion-preview-svg'); result.setAttribute('aria-hidden','true'); }
    return result;
  }

  // One shared WebGL context prevents a gallery from exhausting GPU contexts.
  const gpu = { canvas: null, gl: null, buffer: null, vertex: null, textures: [], programs: new Map(), entries: new Set(), frame: 0, last: 0, cursor: 0, attempted: false };
  function sceneTexture(variant) {
    const c = document.createElement('canvas'); c.width = 320; c.height = 200;
    const ctx = c.getContext('2d');
    ctx.fillStyle = variant === 0 ? '#0a1e27' : '#d9eeec'; ctx.fillRect(0,0,320,200);
    ctx.fillStyle = variant === 0 ? '#6ee7f2' : '#15313a';
    if (variant === 0) { ctx.beginPath(); ctx.arc(267,40,75,0,Math.PI*2); ctx.fill(); }
    else { for (let i=0;i<5;i++) ctx.fillRect(162+i*25,-20,9,260); }
    ctx.fillStyle = variant === 0 ? '#e8f9fa' : '#0a242e';
    ctx.font = '600 54px system-ui'; ctx.fillText(variant === 0 ? 'A' : 'B',28,140);
    ctx.font = '12px monospace'; ctx.fillText(variant === 0 ? 'SCENE / 01' : 'SCENE / 02',28,173);
    return c;
  }
  function noiseTexture() { const c=document.createElement('canvas'); c.width=c.height=64; const ctx=c.getContext('2d'); const data=ctx.createImageData(64,64); let seed=731; for(let i=0;i<data.data.length;i+=4){ seed=(seed*1664525+1013904223)>>>0; const v=seed>>>24; data.data[i]=data.data[i+1]=data.data[i+2]=v; data.data[i+3]=255; } ctx.putImageData(data,0,0); return c; }
  function compileShader(type, code) { const gl=gpu.gl, shader=gl.createShader(type); gl.shaderSource(shader,code); gl.compileShader(shader); if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){gl.deleteShader(shader);throw new Error('Shader compilation failed');}return shader; }
  function initGpu() {
    if (gpu.attempted) return Boolean(gpu.gl); gpu.attempted=true;
    try {
      gpu.canvas=document.createElement('canvas'); gpu.canvas.width=320;gpu.canvas.height=200;
      gpu.gl=gpu.canvas.getContext('webgl',{alpha:false,antialias:false,preserveDrawingBuffer:true,powerPreference:'low-power'});
      if(!gpu.gl)return false;
      const gl=gpu.gl; gpu.vertex=compileShader(gl.VERTEX_SHADER,'attribute vec2 a_position;varying vec2 v_uv;void main(){v_uv=(a_position+1.0)*.5;gl_Position=vec4(a_position,0.0,1.0);}');
      gpu.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,gpu.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
      for(const c of [sceneTexture(0),sceneTexture(1),noiseTexture()]){const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gpu.textures.push(texture);}
      gpu.canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(gpu.frame);gpu.frame=0;for(const entry of gpu.entries) entry.owner.unavailable('webgl');gpu.entries.clear();gpu.programs.clear();gpu.gl=null;});
      return true;
    } catch { gpu.gl=null;return false; }
  }
  function uniformDefaults(code) {
    const defaults = new Map();
    const pattern=/uniform\s+(float|int|bool|vec[234]|ivec[234]|sampler2D)\s+([a-zA-Z_]\w*)\s*(?:\/\*\s*=\s*([^*]+)\*\/)?\s*;[^\n]*/g;
    for(const match of code.matchAll(pattern)){
      const comment=match[3]||(/\/\/\s*=\s*([^\n]+)/.exec(match[0])||[])[1]||'';
      let value;
      if(match[1]==='bool') value=/true/.test(comment)?1:0;
      else { const numeric=(comment.replace(/(?:i?vec[234])\s*\(/g,'').match(/-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/gi)||[]).slice(0,4).map(Number); value=numeric.length?numeric:[.5]; }
      defaults.set(match[2],{type:match[1],value});
    }
    return defaults;
  }
  function shaderProgram(item) {
    const code=typeof item.code==='string'?item.code:'';
    if(code.length>60000 || /#\s*(?:include|extension)|\b(?:while|do)\s*[{(]|\bvoid\s+main\s*\(/.test(stripComments(code)) || !/\bvec4\s+transition\s*\(/.test(code))throw new Error('Unsupported shader');
    const key=item.id+':'+code.length;
    if(gpu.programs.has(key))return gpu.programs.get(key);
    const gl=gpu.gl;
    const fragment=compileShader(gl.FRAGMENT_SHADER,`precision highp float;varying vec2 v_uv;uniform float progress;uniform float ratio;uniform sampler2D ml_from;uniform sampler2D ml_to;vec4 getFromColor(vec2 p){return texture2D(ml_from,p);}vec4 getToColor(vec2 p){return texture2D(ml_to,p);}\n${code}\nvoid main(){gl_FragColor=transition(v_uv);}`);
    const program=gl.createProgram();gl.attachShader(program,gpu.vertex);gl.attachShader(program,fragment);gl.linkProgram(program);gl.deleteShader(fragment);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS)){gl.deleteProgram(program);throw new Error('Shader link failed');}
    const info={program,position:gl.getAttribLocation(program,'a_position'),uniforms:[],defaults:uniformDefaults(code),key};
    for(let i=0;i<gl.getProgramParameter(program,gl.ACTIVE_UNIFORMS);i++){const u=gl.getActiveUniform(program,i);info.uniforms.push({name:u.name,type:u.type,size:u.size,location:gl.getUniformLocation(program,u.name)});}
    gpu.programs.set(key,info);
    if(gpu.programs.size>32){const oldest=gpu.programs.keys().next().value;gl.deleteProgram(gpu.programs.get(oldest).program);gpu.programs.delete(oldest);}
    return info;
  }
  function drawShader(entry, progress) {
    const gl=gpu.gl; if(!gl)return;
    const info=shaderProgram(entry.item);gl.useProgram(info.program);gl.bindBuffer(gl.ARRAY_BUFFER,gpu.buffer);gl.enableVertexAttribArray(info.position);gl.vertexAttribPointer(info.position,2,gl.FLOAT,false,0,0);
    for(let i=0;i<gpu.textures.length;i++){gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,gpu.textures[i]);}
    for(const u of info.uniforms){
      if(u.name==='progress'){gl.uniform1f(u.location,progress);continue;}
      if(u.name==='ratio'){gl.uniform1f(u.location,1.6);continue;}
      if(u.type===gl.SAMPLER_2D){gl.uniform1i(u.location,u.name==='ml_from'?0:u.name==='ml_to'?1:2);continue;}
      let v=info.defaults.get(u.name)?.value??[.5];v=Array.isArray(v)?v:[v];
      const dims=({[gl.FLOAT_VEC2]:2,[gl.FLOAT_VEC3]:3,[gl.FLOAT_VEC4]:4,[gl.INT_VEC2]:2,[gl.INT_VEC3]:3,[gl.INT_VEC4]:4,[gl.BOOL_VEC2]:2,[gl.BOOL_VEC3]:3,[gl.BOOL_VEC4]:4})[u.type]||1;
      while(v.length<dims)v.push(v[v.length-1]??.5);
      if(u.type===gl.FLOAT)gl.uniform1f(u.location,v[0]);
      else if(u.type===gl.FLOAT_VEC2)gl.uniform2fv(u.location,v.slice(0,2));
      else if(u.type===gl.FLOAT_VEC3)gl.uniform3fv(u.location,v.slice(0,3));
      else if(u.type===gl.FLOAT_VEC4)gl.uniform4fv(u.location,v.slice(0,4));
      else if(dims===1)gl.uniform1i(u.location,Math.round(v[0]));
      else if(dims===2)gl.uniform2iv(u.location,v.slice(0,2).map(Math.round));
      else if(dims===3)gl.uniform3iv(u.location,v.slice(0,3).map(Math.round));
      else gl.uniform4iv(u.location,v.slice(0,4).map(Math.round));
    }
    gl.viewport(0,0,320,200);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);entry.ctx.drawImage(gpu.canvas,0,0);entry.canvas.dataset.progress=progress.toFixed(3);entry.canvas.dataset.compiled='true';
  }
  function gpuTick(time) {
    gpu.frame=0;
    if(time-gpu.last>65){
      gpu.last=time;
      const active=[...gpu.entries].filter(e=>e.owner.visible&&!e.owner.paused&&!reduced.matches&&e.owner.root.isConnected);
      for(let i=0;i<Math.min(6,active.length);i++){
        const entry=active[(gpu.cursor+i)%active.length];
        const cycle=((time-entry.started)%4200)/4200;const p=Math.min(1,Math.max(0,(cycle-.13)/.72));
        try{drawShader(entry,p);}catch{entry.owner.unavailable('shader');gpu.entries.delete(entry);}
      }
      gpu.cursor+=6;
    }
    if(gpu.entries.size)gpu.frame=requestAnimationFrame(gpuTick);
  }
  function scheduleGpu(){if(!gpu.frame&&gpu.entries.size)gpu.frame=requestAnimationFrame(gpuTick);}

  const visibility = new IntersectionObserver(entries=>{for(const observed of entries){const instance=[...instances].find(i=>i.root===observed.target);if(instance){instance.visible=observed.isIntersecting;if(instance.gpuEntry)scheduleGpu();}}},{rootMargin:'100px'});
  const cleanup = new MutationObserver(()=>{for(const instance of instances) if(instance.attached&&!instance.root.isConnected)instance.destroy();else if(instance.root.isConnected)instance.attached=true;});
  function create(item, options = {}) {
    const lang=options.lang==='en'?'en':'ko', words=labels[lang];
    const root=element('div','motion-preview'+(options.compact?' compact':''));
    const referenceMode=['related-asset','illustration'].includes(options.reference?.mode)?options.reference.mode:null;
    if(referenceMode){
      root.classList.add('motion-preview-reference');root.dataset.referencePreview=referenceMode;root.dataset.referenceId=String(options.reference.id||'').slice(0,250);
      const caption=lang==='ko'?(referenceMode==='related-asset'?'관련 로컬 에셋':options.compact?'Motion Lab 재현':'Motion Lab 개념 재현'):(referenceMode==='related-asset'?(options.compact?'Related asset':'Related local asset'):(options.compact?'Motion Lab study':'Motion Lab concept illustration'));
      root.append(element('span','motion-preview-reference-label',caption));
    }
    if(item.domain==='design'||item.analysis?.domain==='design')root.classList.add('motion-preview-design');
    root.dataset.itemId=String(item.id||'').slice(0,160);
    root.dataset.assetType=String(item.analysis?.assetType||item.category||'').slice(0,32);
    const stage=element('div','motion-preview-stage');const note=element('p','motion-preview-note');root.append(stage,note);
    const instance={root,stage,note,lang,paused:Boolean(options.paused||reduced.matches),visible:true,attached:false,interaction:Boolean(options.interaction),gpuEntry:null,svg:null,frame:null,destroy(){visibility.unobserve(root);if(this.gpuEntry)gpu.entries.delete(this.gpuEntry);instances.delete(this);if(!gpu.entries.size){cancelAnimationFrame(gpu.frame);gpu.frame=0;}},unavailable(key){if(this.gpuEntry)gpu.entries.delete(this.gpuEntry);stage.replaceChildren();const box=element('div','motion-preview-unavailable');box.append(element('strong','',words[key]||words.invalid));if(key==='reference')box.append(element('span','',words.noPreview));stage.append(box);note.textContent='';root.dataset.state='unavailable';root.dataset.reason=key;},setPaused(value){this.paused=Boolean(value||reduced.matches);if(this.svg){if(this.paused)this.svg.pauseAnimations?.();else this.svg.unpauseAnimations?.();}if(this.frame)refreshCss();if(this.gpuEntry){if(this.paused)try{drawShader(this.gpuEntry,.5);}catch{this.unavailable('shader');}else scheduleGpu();}},setInteraction(value){this.interaction=Boolean(value);if(this.frame)refreshCss();},restart(){if(this.frame)refreshCss();if(this.svg)this.svg.setCurrentTime?.(0);if(this.gpuEntry)this.gpuEntry.started=performance.now();}};
    function refreshCss(){const built=cssDocument(item,instance.paused,instance.interaction);if(!built){instance.unavailable('invalid');return;}instance.frame.srcdoc=built.document;}
    root.destroy=()=>instance.destroy();root.setPaused=value=>instance.setPaused(value);root.setInteraction=value=>instance.setInteraction(value);root.restart=()=>instance.restart();
    root.setProgress=value=>{if(instance.gpuEntry&&Number.isFinite(value))drawShader(instance.gpuEntry,Math.max(0,Math.min(1,value)));};
    instances.add(instance);visibility.observe(root);
    const renderer=item.analysis?.preview?.renderer || (item.kind==='reference'?'none':item.kind==='image'?'image':item.preview?.type==='gradient'?'gradient':item.kind==='palette'?'palette':item.language==='svg'?'svg':item.language==='glsl'?'glsl':item.language==='css'?'css':'none');
    root.dataset.renderer=renderer;root.dataset.state='ready';
    try {
      const colors=colorsOf(item);
      if(renderer==='palette'&&colors.length){const strips=element('div','motion-preview-colors');for(const color of colors){const strip=element('div','motion-preview-swatch');strip.style.backgroundColor=color;strip.style.color=paletteTextColor(color);strip.append(element('span','',color.toUpperCase()));strips.append(strip);}stage.append(strips);note.textContent=words.palette;}
      else if(renderer==='gradient'&&colors.length){const gradient=element('div','motion-preview-gradient');gradient.style.background=`linear-gradient(125deg,${colors.join(',')})`;stage.append(gradient);note.textContent=words.gradient;}
      else if(renderer==='css'){const built=cssDocument(item,instance.paused,instance.interaction);if(!built){instance.unavailable('invalid');return root;}const frame=element('iframe','motion-preview-frame');frame.setAttribute('sandbox','');frame.referrerPolicy='no-referrer';frame.tabIndex=-1;frame.title=String(item.title||'CSS preview').slice(0,180);frame.srcdoc=built.document;stage.append(frame);instance.frame=frame;note.textContent=item.analysis?.domain==='design'||item.domain==='design'?(lang==='ko'?'원본 CSS 디자인':'Original CSS design'):words[built.composition?'composition':'css'];}
      else if(renderer==='svg'){const svg=sanitizedSvg(item.code);if(!svg){instance.unavailable('invalid');return root;}stage.append(svg);instance.svg=svg;note.textContent=(item.domain==='design'||item.analysis?.domain==='design')?(lang==='ko'?'원본 SVG 디자인':'Original SVG design'):words.svg;if(instance.paused)requestAnimationFrame(()=>{svg.setCurrentTime?.(.8);svg.pauseAnimations?.();});}
      else if(renderer==='image'){
        const image=item.image,path=image?.path;
        if(typeof path!=='string'||!/^assets\/materials\/[a-z0-9][a-z0-9-]{0,159}\.jpg$/.test(path)||image.mime!=='image/jpeg'||!Number.isInteger(image.width)||!Number.isInteger(image.height)||image.width<32||image.height<32||image.width>1024||image.height>1024){instance.unavailable('invalid');return root;}
        const visual=element('img','motion-preview-image');visual.alt=String(item.title||'Material').slice(0,300);visual.width=image.width;visual.height=image.height;visual.decoding='async';visual.loading=options.compact?'lazy':'eager';visual.referrerPolicy='no-referrer';visual.addEventListener('error',()=>instance.unavailable('invalid'));visual.src='./'+path;stage.append(visual);note.textContent=lang==='ko'?'저장된 소재 이미지 · 정적 디자인':'Stored material image · static design';
      }
      else if(renderer==='glsl'){if(!initGpu()){instance.unavailable('webgl');return root;}const canvas=element('canvas','motion-preview-canvas');canvas.width=320;canvas.height=200;stage.append(canvas);const entry={item,canvas,ctx:canvas.getContext('2d'),started:performance.now(),owner:instance};instance.gpuEntry=entry;gpu.entries.add(entry);drawShader(entry,.45);note.textContent=item.preview?.scene==='procedural'?words.procedural:words.glsl;scheduleGpu();}
      else instance.unavailable('reference');
    } catch { instance.unavailable(renderer==='glsl'?'shader':'invalid'); }
    if(referenceMode&&root.dataset.state!=='unavailable')note.textContent=options.compact?(lang==='ko'?(referenceMode==='related-asset'?'원본 화면 아님':'원본 소스 아님'):(referenceMode==='related-asset'?'Not the original page':'Not original source')):lang==='ko'?(referenceMode==='related-asset'?'관련 예시 · 원본 화면 아님':'개념 재현 · 원본 소스 아님'):(referenceMode==='related-asset'?'Related example / not the original page':'Concept illustration / not original source');
    return root;
  }
  cleanup.observe(document.documentElement,{childList:true,subtree:true});
  reduced.addEventListener?.('change',()=>{for(const instance of instances)instance.setPaused(instance.paused);});
  window.MotionPreview={create,destroy:root=>root?.destroy?.(),setPaused:value=>{for(const instance of instances)instance.setPaused(value);},diagnostics:()=>({instances:instances.size,gpuContexts:gpu.gl?1:0,shaderPrograms:gpu.programs.size,activeShaders:gpu.entries.size}),sanitizeSvg:sanitizedSvg};
})();
