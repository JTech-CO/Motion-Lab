// ═══════════════════════════════════════════
// INKJET — Batch 4: Final 42 to reach 500
// ═══════════════════════════════════════════

import type { PatternConfig, PatternMeta, PatternCategory } from '../types'

type RenderFn = (c: Required<PatternConfig>, w: number, h: number) => string
type RegFn = (name: string, category: PatternCategory, desc: string, tags: string[], fn: RenderFn) => void

function srng(seed: number) { let s = seed; return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646 } }
const TAU = Math.PI * 2
function ci(cx: number, cy: number, r: number, f: string, o = 1) { return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${f}" opacity="${o}"/>` }
function rc(x: number, y: number, w: number, h: number, f: string, o = 1, rx = 0) { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${f}" opacity="${o}"${rx ? ` rx="${rx}"` : ''}/>` }
function ln(x1: number, y1: number, x2: number, y2: number, s: string, sw: number, o = 1) { return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${s}" stroke-width="${sw}" opacity="${o}"/>` }
function pa(d: string, f: string, s: string, sw: number, o = 1) { return `<path d="${d}" fill="${f}" stroke="${s}" stroke-width="${sw}" opacity="${o}"/>` }

export function registerBatch4(reg: RegFn) {

// ═══ MORE CHECKS (13) ═══
reg('checkerboard','check','Classic checkerboard',['checker','classic'], (c,w,h) => rc(0,0,w/2,h/2,c.color,c.opacity*0.1) + rc(w/2,h/2,w/2,h/2,c.color,c.opacity*0.1))
reg('micro-check','check','Tiny micro check',['micro','fine'], (c,w,h) => { const sz=w/4; let s=''; for(let r=0;r<4;r++) for(let co=0;co<4;co++) if((r+co)%2===0) s+=rc(co*sz,r*sz,sz,sz,c.color,c.opacity*0.06); return s })
reg('natte','check','Natte basket check',['natte','weave'], (c,w,h) => rc(0,0,w*0.25,h*0.5,c.color,c.opacity*0.06) + rc(w*0.25,0,w*0.25,h*0.5,c.color,c.opacity*0.1) + rc(w*0.5,h*0.5,w*0.25,h*0.5,c.color,c.opacity*0.06) + rc(w*0.75,h*0.5,w*0.25,h*0.5,c.color,c.opacity*0.1))
reg('district-check','check','District/estate check',['district','hunting'], (c,w,h) => rc(0,0,w,h,'none',0) + `<rect x="0" y="0" width="${w}" height="${h}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth}" opacity="${c.opacity*0.06}"/>` + ln(0,0,w,h,c.color,c.strokeWidth*0.3,c.opacity*0.04))
reg('graph-check','check','Graph paper fine check',['graph','paper'], (c,w,h) => { let s=''; for(let i=0;i<=4;i++) { s+=ln(i*w/4,0,i*w/4,h,c.color,c.strokeWidth*0.2,c.opacity*0.04); s+=ln(0,i*h/4,w,i*h/4,c.color,c.strokeWidth*0.2,c.opacity*0.04) } return s })
reg('vichy','check','Vichy gingham large',['vichy','french'], (c,w,h) => rc(0,0,w/2,h,c.color,c.opacity*0.06) + rc(0,0,w,h/2,c.color,c.opacity*0.06))
reg('pixel-check','check','Pixel-scale tiny check',['pixel','digital'], (c,w,h) => { const sz=w/6; let s=''; for(let r=0;r<6;r++) for(let co=0;co<6;co++) if((r+co)%2===0) s+=rc(co*sz,r*sz,sz,sz,c.color,c.opacity*0.04); return s })
reg('twill-check','check','Twill weave diagonal check',['twill','diagonal'], (c,w,h) => rc(0,0,w/2,h/2,c.color,c.opacity*0.06) + rc(w/2,h/2,w/2,h/2,c.color,c.opacity*0.06) + ln(0,0,w/2,h/2,c.color,c.strokeWidth*0.2,c.opacity*0.04) + ln(w/2,h/2,w,h,c.color,c.strokeWidth*0.2,c.opacity*0.04))
reg('tatami','check','Tatami mat rectangular grid',['tatami','japanese'], (c,w,h) => rc(0,0,w*0.48,h*0.48,'none',c.opacity) + `<rect x="1" y="1" width="${w*0.48-2}" height="${h*0.48-2}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth*0.3}" opacity="${c.opacity*0.06}"/>` + `<rect x="${w*0.52}" y="${h*0.52}" width="${w*0.48-2}" height="${h*0.48-2}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth*0.3}" opacity="${c.opacity*0.06}"/>`)
reg('harlequin','check','Harlequin diamond check',['harlequin','theatrical'], (c,w,h) => pa(`M${w/2},0 L${w},${h/2} L${w/2},${h} L0,${h/2} Z`,c.color,'none',0,c.opacity*0.06))
reg('windowpane-bold','check','Bold windowpane lines',['windowpane','bold'], (c,w,h) => ln(w*0.5,0,w*0.5,h,c.color,c.strokeWidth*1.5,c.opacity*0.08) + ln(0,h*0.5,w,h*0.5,c.color,c.strokeWidth*1.5,c.opacity*0.08))
reg('overcheck','check','Overcheck fine overlay',['overcheck','subtle'], (c,w,h) => ln(w*0.33,0,w*0.33,h,c.color,c.strokeWidth*0.2,c.opacity*0.04) + ln(w*0.66,0,w*0.66,h,c.color,c.strokeWidth*0.2,c.opacity*0.04) + ln(0,h*0.33,w,h*0.33,c.color,c.strokeWidth*0.2,c.opacity*0.04) + ln(0,h*0.66,w,h*0.66,c.color,c.strokeWidth*0.2,c.opacity*0.04))
reg('prince-of-wales','check','Prince of Wales check',['pow','suiting'], (c,w,h) => rc(0,0,w/2,h/2,c.color,c.opacity*0.04) + rc(w/2,h/2,w/2,h/2,c.color,c.opacity*0.04) + ln(0,h*0.25,w,h*0.25,c.color,c.strokeWidth*0.3,c.opacity*0.06) + ln(0,h*0.75,w,h*0.75,c.color,c.strokeWidth*0.3,c.opacity*0.06) + ln(w*0.25,0,w*0.25,h,c.color,c.strokeWidth*0.3,c.opacity*0.06) + ln(w*0.75,0,w*0.75,h,c.color,c.strokeWidth*0.3,c.opacity*0.06))

// ═══ MORE STRIPES (12) ═══
reg('bengal-stripe','stripe','Bengal wide stripe',['bengal','wide'], (c,w,h) => rc(0,0,w*0.45,h,c.color,c.opacity*0.08))
reg('ticking-fine','stripe','Fine ticking stripe',['ticking','fine'], (c,w,h) => ln(w*0.33,0,w*0.33,h,c.color,c.strokeWidth*0.4,c.opacity*0.06) + ln(w*0.66,0,w*0.66,h,c.color,c.strokeWidth*0.4,c.opacity*0.06))
reg('multistripe','stripe','Multiple weight stripes',['multi','varied'], (c,w,h) => rc(w*0.1,0,w*0.03,h,c.color,c.opacity*0.1) + rc(w*0.2,0,w*0.08,h,c.color,c.opacity*0.05) + rc(w*0.5,0,w*0.03,h,c.color,c.opacity*0.1) + rc(w*0.7,0,w*0.12,h,c.color,c.opacity*0.04))
reg('hairline-stripe','stripe','Hairline ultra-thin stripe',['hairline','minimal'], (c,w,h) => ln(w*0.5,0,w*0.5,h,c.color,0.5,c.opacity*0.06))
reg('bayadere','stripe','Horizontal bayadère stripe',['bayadere','horizontal'], (c,w,h) => rc(0,0,w,h*0.35,c.color,c.opacity*0.06) + rc(0,h*0.5,w,h*0.15,c.color,c.opacity*0.1))
reg('deckchair','stripe','Bold deckchair stripe',['deckchair','seaside'], (c,w,h) => rc(0,0,w*0.5,h,c.color,c.opacity*0.12))
reg('blazer-stripe','stripe','Blazer two-tone stripe',['blazer','preppy'], (c,w,h) => rc(w*0.15,0,w*0.1,h,c.color,c.opacity*0.08) + rc(w*0.75,0,w*0.1,h,c.color,c.opacity*0.08))
reg('breton-stripe','stripe','Breton nautical stripe',['breton','nautical'], (c,w,h) => { let s=''; for(let i=0;i<4;i++) s+=rc(0,i*h/3.5+h*0.05,w,h*0.15,c.color,c.opacity*0.1); return s })
reg('mattress-stripe','stripe','Mattress herringbone stripe',['mattress','herringbone'], (c,w,h) => pa(`M${w*0.3},0 L${w*0.5},${h*0.5} L${w*0.3},${h} M${w*0.7},0 L${w*0.5},${h*0.5} L${w*0.7},${h}`,'none',c.color,c.strokeWidth*0.5,c.opacity*0.08))
reg('candy-cane','stripe','Candy cane twist stripe',['candy','christmas'], (c,w,h) => pa(`M0,0 L${w*0.3},${h} L${w*0.5},${h} L${w*0.2},0 Z`,c.color,'none',0,c.opacity*0.06))
reg('rainbow-stripe','stripe','Evenly spaced thin stripes',['rainbow','colorful'], (c,w,h) => { let s=''; for(let i=0;i<6;i++) s+=ln(w*(0.1+i*0.15),0,w*(0.1+i*0.15),h,c.color,c.strokeWidth*0.3,c.opacity*(0.03+i*0.01)); return s })
reg('oxford-stripe','stripe','Oxford cloth buttondown stripe',['oxford','shirting'], (c,w,h) => { let s=''; for(let x=0;x<w;x+=4) s+=rc(x,0,2,h,c.color,c.opacity*0.03); return s })

// ═══ MORE FASHION (1) ═══
reg('snakeskin-diamond','fashion','Diamond snakeskin scales',['snake','diamond'], (c,w,h) => pa(`M${w/2},0 L${w},${h/2} L${w/2},${h} L0,${h/2} Z`,'none',c.color,c.strokeWidth*0.4,c.opacity*0.08) + ln(w*0.25,h*0.25,w*0.75,h*0.75,c.color,c.strokeWidth*0.2,c.opacity*0.04))

// ═══ MORE MODERN (1) ═══
reg('gradient-dot','modern','Gradient-sized dot grid',['gradient','dot'], (c,w,h) => { let s=''; for(let r=0;r<3;r++) for(let co=0;co<3;co++) { const t=(r*3+co)/9; s+=ci(w*(0.2+co*0.3),h*(0.2+r*0.3),w*0.02+t*w*0.04,c.color,c.opacity*(0.03+t*0.06)) } return s })

// ═══ MORE ABSTRACT (1) ═══
reg('klein-bottle','abstract','Klein bottle cross-section',['klein','topology'], (c,w,h) => pa(`M${w*0.2},${h*0.5} Q${w*0.2},${h*0.1} ${w*0.5},${h*0.1} Q${w*0.8},${h*0.1} ${w*0.8},${h*0.5} Q${w*0.8},${h*0.9} ${w*0.5},${h*0.7} Q${w*0.2},${h*0.5} ${w*0.5},${h*0.3} Q${w*0.8},${h*0.1} ${w*0.5},${h*0.5}`,'none',c.color,c.strokeWidth*0.5,c.opacity*0.08))

// ═══ MORE FLORAL (1) ═══
reg('protea','floral','Protea geometric bloom',['protea','african'], (c,w,h) => { let s=''; for(let i=0;i<8;i++) { const a=i*TAU/8,r1=w*0.12,r2=w*0.28; s+=pa(`M${w/2+Math.cos(a)*r1},${h/2+Math.sin(a)*r1} L${w/2+Math.cos(a-0.15)*r2},${h/2+Math.sin(a-0.15)*r2} L${w/2+Math.cos(a+0.15)*r2},${h/2+Math.sin(a+0.15)*r2} Z`,c.color,'none',0,c.opacity*0.03) } return s + ci(w/2,h/2,w*0.1,c.color,c.opacity*0.06) })

// ═══ MORE RETRO (4) ═══
reg('record-label','retro','Vinyl record center label',['vinyl','label'], (c,w,h) => ci(w/2,h/2,w*0.25,'none',0) + `<circle cx="${w/2}" cy="${h/2}" r="${w*0.25}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth}" opacity="${c.opacity*0.08}"/>` + ci(w/2,h/2,w*0.04,c.color,c.opacity*0.1) + `<circle cx="${w/2}" cy="${h/2}" r="${w*0.35}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth*0.3}" opacity="${c.opacity*0.04}"/>`)
reg('cathode-ray','retro','CRT phosphor scanlines',['crt','monitor'], (c,w,h) => { let s=''; for(let y=0;y<h;y+=3) s+=rc(0,y,w,1,c.color,c.opacity*0.03); return s })
reg('dot-matrix-print','retro','Dot matrix printer output',['dotmatrix','printer'], (c,w,h) => { const rng=srng(c.seed); let s=''; const sz=w/8; for(let r=0;r<4;r++) for(let co=0;co<8;co++) if(rng()>0.4) s+=ci(co*sz+sz/2,r*h/4+h/8,0.7,c.color,c.opacity*0.06); return s })
reg('ticker-tape','retro','Stock ticker tape dots',['ticker','stocks'], (c,w,h) => { const rng=srng(c.seed); let s=ln(0,h/2,w,h/2,c.color,c.strokeWidth*0.3,c.opacity*0.04); for(let i=0;i<6;i++) s+=ci(rng()*w,h/2+(rng()-0.5)*h*0.3,0.8,c.color,c.opacity*0.06); return s })

// ═══ MORE ISLAMIC (2) ═══
reg('star-10fold','islamic','Ten-pointed Islamic star',['star','decagonal'], (c,w,h) => { const cx=w/2,cy=h/2,r=w*0.4; let d=''; for(let i=0;i<20;i++) { const a=i*Math.PI/10,ri=i%2===0?r:r*0.45; d+=(i===0?'M':'L')+`${cx+Math.cos(a)*ri},${cy+Math.sin(a)*ri} ` } return pa(d+'Z','none',c.color,c.strokeWidth*0.5,c.opacity*0.1) })
reg('tile-octagon','islamic','Octagon-cross tile pattern',['octagon','cross'], (c,w,h) => { const d=w*0.2; return pa(`M${d},0 L${w-d},0 L${w},${d} L${w},${h-d} L${w-d},${h} L${d},${h} L0,${h-d} L0,${d} Z`,'none',c.color,c.strokeWidth*0.5,c.opacity*0.08) })

// ═══ MORE NATURE-EXT (3) ═══
reg('tide-ripple','nature-ext','Beach tide ripple lines',['tide','beach'], (c,w,h) => { let s=''; for(let i=0;i<5;i++) { const y=h*(0.15+i*0.17); s+=pa(`M0,${y} Q${w*0.25},${y-2} ${w*0.5},${y+1} Q${w*0.75},${y+3} ${w},${y-1}`,'none',c.color,c.strokeWidth*0.3,c.opacity*(0.03+i*0.01)) } return s })
reg('lichen','nature-ext','Lichen growth patches',['lichen','rock'], (c,w,h) => { const rng=srng(c.seed); let s=''; for(let i=0;i<Math.ceil(c.density*6);i++) { const cx=rng()*w,cy=rng()*h,rx=1+rng()*w*0.08,ry=0.8+rng()*h*0.06; s+=`<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${c.color}" opacity="${c.opacity*(0.02+rng()*0.04)}"/>` } return s })
reg('erosion','nature-ext','Erosion weathering marks',['erosion','geological'], (c,w,h) => { const rng=srng(c.seed); let s=''; for(let i=0;i<Math.ceil(c.density*6);i++) { const x=rng()*w,y=rng()*h; s+=pa(`M${x},${y} Q${x+rng()*6-3},${y+rng()*4-2} ${x+rng()*8-4},${y+rng()*6-3}`,'none',c.color,c.strokeWidth*0.3,c.opacity*(0.03+rng()*0.05)) } return s })

// ═══ MORE ARCHITECTURAL (2) ═══
reg('finial','architectural','Finial spire ornament',['finial','spire'], (c,w,h) => pa(`M${w/2},${h*0.05} Q${w*0.55},${h*0.15} ${w*0.55},${h*0.3} L${w*0.6},${h*0.4} L${w*0.55},${h*0.5} L${w*0.55},${h*0.9} L${w*0.45},${h*0.9} L${w*0.45},${h*0.5} L${w*0.4},${h*0.4} L${w*0.45},${h*0.3} Q${w*0.45},${h*0.15} ${w/2},${h*0.05}`,'none',c.color,c.strokeWidth*0.4,c.opacity*0.08))
reg('rustication','architectural','Rusticated stone blocks',['rustication','stone'], (c,w,h) => `<rect x="1" y="1" width="${w-2}" height="${h*0.45}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth}" opacity="${c.opacity*0.06}" rx="1"/>` + `<rect x="${w*0.3}" y="${h*0.55}" width="${w*0.7-1}" height="${h*0.43}" fill="none" stroke="${c.color}" stroke-width="${c.strokeWidth}" opacity="${c.opacity*0.06}" rx="1"/>`)

// ═══ MORE TEXTILE (2) ═══
reg('dobby-weave','textile','Dobby small geometric weave',['dobby','woven'], (c,w,h) => { const sz=w/4; let s=''; for(let r=0;r<4;r++) for(let co=0;co<4;co++) if((r+co)%3===0) s+=rc(co*sz+1,r*sz+1,sz-2,sz-2,c.color,c.opacity*0.05); return s })
reg('birdseye','textile','Birdseye diamond weave',['birdseye','diamond'], (c,w,h) => pa(`M${w/2},${h*0.15} L${w*0.85},${h/2} L${w/2},${h*0.85} L${w*0.15},${h/2} Z`,'none',c.color,c.strokeWidth*0.3,c.opacity*0.06) + ci(w/2,h/2,w*0.04,c.color,c.opacity*0.05))

}
