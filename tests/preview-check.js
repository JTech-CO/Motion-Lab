'use strict';
// Copy this and preview-check.html to dist/_preview-qa.* for a local browser run.
document.getElementById('run').addEventListener('click', async () => {
  const output=document.getElementById('result'), samples=document.getElementById('samples');
  const button=document.getElementById('run');button.disabled=true;
  const report={total:0,ready:0,byRenderer:{},failures:[],shaderEndpointChecks:0,shaderEndpointDifferent:0,shaderDifferentFrames:0,shaderDiscreteFrames:[],security:{}};
  try {
    const catalog=await (await fetch('/catalog.json',{cache:'no-store'})).json();
    const parameters=new URLSearchParams(location.search), renderer=parameters.get('renderer'), prefix=parameters.get('prefix')||'';
    const items=catalog.items.filter(item=>item.kind!=='reference'&&(!prefix||item.id.startsWith(prefix))&&(renderer?item.language===renderer:['css','glsl','svg'].includes(item.language)));
    function sum(canvas){const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;let hash=2166136261;for(let i=0;i<pixels.length;i+=13)hash=Math.imul(hash^pixels[i],16777619);return hash>>>0;}
    for(let offset=0;offset<items.length;offset+=8){
      samples.replaceChildren();
      const previews=[];
      for(const item of items.slice(offset,offset+8)){
        const preview=MotionPreview.create(item,{compact:true,paused:true,lang:'en'});samples.append(preview);previews.push(preview);
        report.total++;const renderer=preview.dataset.renderer;
        report.byRenderer[renderer]??={total:0,ready:0};report.byRenderer[renderer].total++;
        if(preview.dataset.state==='ready'){report.ready++;report.byRenderer[renderer].ready++;}
        else report.failures.push({id:item.id,renderer,reason:preview.dataset.reason});
        const canvas=preview.querySelector('canvas');
        if(canvas&&preview.dataset.state==='ready'){
          preview.setProgress(0);const from=sum(canvas);preview.setProgress(.5);const middle=sum(canvas);preview.setProgress(1);const to=sum(canvas);
          report.shaderEndpointChecks++;if(from!==to)report.shaderEndpointDifferent++;
          if(from!==to&&middle!==from&&middle!==to)report.shaderDifferentFrames++;
          else report.shaderDiscreteFrames.push({id:item.id,from,middle,to});
        }
      }
      output.textContent=JSON.stringify({...report,progress:`${Math.min(offset+8,items.length)}/${items.length}`},null,2);
      await new Promise(resolve=>setTimeout(resolve,25));
      previews.forEach(preview=>preview.destroy());
    }
    const maliciousCss=MotionPreview.create({id:'security-url',kind:'code',language:'css',code:'.motion-sample{background:url(https://example.invalid/a)}'},{paused:true,lang:'en'});
    report.security.cssExternalUrlBlocked=maliciousCss.dataset.state==='unavailable';maliciousCss.destroy();
    const shorthand=MotionPreview.create({id:'css-shorthand-regression',kind:'code',language:'css',code:'.motion-sample{--accent:#69e6f7;background:var(--accent);border-radius:12px;width:60px;height:60px}'},{paused:true,lang:'en'});
    const documentText=shorthand.querySelector('iframe')?.srcdoc||'';
    report.security.cssVariableShorthandPreserved=documentText.includes('background:var(--accent)')&&documentText.includes('border-radius:12px');shorthand.destroy();
    const standalone=MotionPreview.create({id:'standalone-target-regression',kind:'code',language:'css',category:'animation',analysis:{assetType:'animation',preview:{renderer:'css',dom:{tag:'div',className:'motion-sample'}}},code:'@keyframes actual{to{transform:translateX(40px)}}.motion-sample{animation:actual 1s infinite}'},{paused:true,lang:'en'});
    report.security.cssStandaloneVisibleTarget=Boolean(standalone.querySelector('iframe')?.srcdoc.includes('width:54px'));standalone.destroy();
    const safe=MotionPreview.sanitizeSvg('<svg xmlns="http://www.w3.org/2000/svg"><script>bad()</script><circle r="4" onclick="bad()"/><use href="https://example.invalid/a"/><animate attributeName="href" values="javascript:bad()"/></svg>');
    report.security.svgActiveContentBlocked=Boolean(safe&&!safe.querySelector('script,animate')&&!safe.querySelector('[onclick],[href]'));
    report.security.svgEntitiesBlocked=MotionPreview.sanitizeSvg('<!DOCTYPE svg [<!ENTITY x SYSTEM "https://example.invalid/a">]><svg xmlns="http://www.w3.org/2000/svg"/>')===null;
    const smil=MotionPreview.sanitizeSvg('<svg xmlns="http://www.w3.org/2000/svg"><g style="transform-origin:12px 12px;background:url(https://example.invalid/a)"><set attributeName="opacity" to="1" begin="0.4s" fill="freeze"/><set attributeName="href" to="javascript:bad()"/></g></svg>');
    report.security.svgSetAndSafeOriginPreserved=Boolean(smil?.querySelector('set[attributeName="opacity"][fill="freeze"]')&&smil.querySelector('g').style.transformOrigin==='12px 12px'&&!smil.querySelector('g').style.background&&!smil.querySelector('set[attributeName="href"]'));
    const tokens=MotionPreview.create({id:'safe-variables-regression',kind:'code',language:'css',code:'.heading{animation-delay:calc(var(--i)*.1s);color:var(--ink)}',preview:{dom:{tag:'h1',className:'heading',text:'Actual text',variables:{'--i':'2','--bad':'url(https://example.invalid/a)'}},variables:{'--ink':'#00ffff'}}},{paused:true,lang:'en'});
    const tokenDocument=tokens.querySelector('iframe')?.srcdoc||'';
    report.security.cssSourceVariablesPreserved=tokenDocument.includes('--ink:#00ffff;')&&tokenDocument.includes('--i:2;')&&!tokenDocument.includes('example.invalid')&&tokenDocument.includes('<h1');tokens.destroy();
    const localFilter=MotionPreview.sanitizeSvg('<svg xmlns="http://www.w3.org/2000/svg"><defs><filter id="goo"><feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="y"/><feColorMatrix in="y" mode="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 18 -7" result="z"/><feBlend in="SourceGraphic" in2="z"/><feImage href="https://example.invalid/a"/><animate attributeName="stdDeviation" to="999"/></filter></defs><g filter="url(#goo)" onclick="bad()"><circle r="4"/></g></svg>');
    const localFilterId=localFilter?.querySelector('filter')?.getAttribute('id');
    report.security.svgLocalFiltersPreserved=Boolean(localFilterId?.startsWith('ml-svg-')&&localFilter.querySelector('g').getAttribute('filter')===`url(#${localFilterId})`&&localFilter.querySelector('feGaussianBlur').getAttribute('stdDeviation')==='1.5'&&localFilter.querySelector('feColorMatrix').getAttribute('values').endsWith('18 -7')&&localFilter.querySelector('feBlend').getAttribute('in2')==='z'&&!localFilter.querySelector('feImage,animate,[onclick]'));
    const boundedFilters=MotionPreview.sanitizeSvg(`<svg xmlns="http://www.w3.org/2000/svg"><defs>${Array.from({length:9},(_,i)=>`<filter id="f${i}"><feGaussianBlur stdDeviation="${i===0?'41':'1'}"/></filter>`).join('')}</defs><g filter="url(https://example.invalid/a)"/><image href="https://example.invalid/a"/></svg>`);
    report.security.svgFiltersBounded=Boolean(boundedFilters&&boundedFilters.querySelectorAll('filter').length===8&&!boundedFilters.querySelector('feGaussianBlur[stdDeviation="41"],g[filter],image'));
    const field=MotionPreview.create({id:'readonly-input-regression',kind:'code',language:'css',code:'.field:focus-visible{outline:1px solid #00ffff}.field::placeholder{color:#00ffff}',preview:{dom:{tag:'input',className:'field',placeholder:'" onfocus="bad()'}}},{paused:true,interaction:true,lang:'en'});
    const fieldDocument=field.querySelector('iframe')?.srcdoc||'';
    report.security.cssReadonlyInputAndFocusPreserved=fieldDocument.includes('type="text" readonly tabindex="-1"')&&fieldDocument.includes('placeholder="&quot; onfocus=&quot;bad()"')&&fieldDocument.includes('.field.preview-active')&&!fieldDocument.includes('.preview-active-visible')&&fieldDocument.includes('.field::placeholder');field.destroy();
    const alphaPalette=MotionPreview.create({id:'alpha-palette-regression',kind:'palette',language:'json',colors:['#ffffff00','#ffffffff']},{paused:true,lang:'en'});
    const alphaSwatches=[...alphaPalette.querySelectorAll('.motion-preview-swatch')];
    report.security.paletteAlphaValuesAndContrastPreserved=alphaSwatches.length===2&&alphaSwatches[0].style.color==='rgb(247, 255, 255)'&&alphaSwatches[1].style.color==='rgb(6, 18, 21)'&&alphaSwatches[0].textContent==='#FFFFFF00';alphaPalette.destroy();
    samples.replaceChildren();report.diagnostics=MotionPreview.diagnostics();report.complete=true;
    output.textContent=JSON.stringify(report,null,2);output.dataset.complete='true';
  } catch(error) {output.textContent='Validation failed: '+String(error.message).slice(0,120);output.dataset.complete='error';}
  finally {button.disabled=false;}
});
