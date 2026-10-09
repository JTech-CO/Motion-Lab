'use strict';
// Runs trusted frontend code against a small DOM model. This is a behavior check,
// not browser rendering or execution of collected asset code.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

class Element {
  constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.attributes={};this.events=new Map();this.dataset={};this.className='';this.classList={add(){},remove(){},contains(){return false;}};this._text='';this._value=undefined;this.scrollTop=0;this.scrollLeft=0;this.disabled=false;this.open=false;this.isContentEditable=false;}
  set id(value){this._id=value;this.ownerDocument.ids.set(value,this);}
  get id(){return this._id||'';}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  get options(){return this.children.filter(child=>child.tagName==='OPTION');}
  set value(value){this._value=String(value);}
  get value(){return this._value??this.options.find(option=>option.selected)?.value??this.options[0]?.value??'';}
  get isConnected(){return true;}
  append(...values){for(const value of values){if(value.tagName==='#FRAGMENT'){this.append(...value.children);continue;}value.parentElement=this;this.children.push(value);}}
  replaceChildren(...values){this.children=[];this._text='';this.append(...values);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
  addEventListener(name,listener){if(!this.events.has(name))this.events.set(name,[]);this.events.get(name).push(listener);}
  dispatch(name,event={}){for(const listener of this.events.get(name)||[])listener({...event,target:this});}
  focus(){this.ownerDocument.activeElement=this;}
  getClientRects(){return [1];}
  scrollIntoView(){}
  matches(selector){return selector==='pre.code-block'&&this.tagName==='PRE'&&this.className==='code-block';}
  querySelectorAll(selector){const result=[];for(const child of this.children){if(selector.includes('button')&&child.tagName==='BUTTON'||selector.includes('select')&&child.tagName==='SELECT'||selector==='a'&&child.tagName==='A'||selector==='[data-item-id]'&&child.dataset.itemId)result.push(child);result.push(...child.querySelectorAll(selector));}return result;}
  querySelector(selector){if(selector==='[role="tab"][aria-selected="true"]')return this.querySelectorAll('button').find(child=>child.getAttribute('role')==='tab'&&child.getAttribute('aria-selected')==='true')||null;return this.querySelectorAll(selector)[0]||null;}
}
class Select extends Element {}
class Input extends Element {}
class TextArea extends Element {}
const document={ids:new Map(),activeElement:null,createElement(tag){const Type=tag==='select'?Select:tag==='input'?Input:tag==='textarea'?TextArea:Element;return new Type(tag,this);},createDocumentFragment(){return new Element('#fragment',this);},getElementById(id){return this.ids.get(id)||null;},querySelectorAll(){return [];}};
for(const id of ['detail-dialog','detail-content','detail-close','gallery','search-input','toast']){const element=document.createElement(id==='search-input'?'input':'div');element.id=id;}
document.getElementById('detail-dialog').open=true;
const previews=[],copies=[];
const context={document,HTMLElement:Element,HTMLSelectElement:Select,HTMLInputElement:Input,HTMLTextAreaElement:TextArea,URL,WeakMap,Map,Set,Promise,JSON,Object,Array,String,Number,Boolean,Math,matchMedia:()=>({matches:false}),requestAnimationFrame:callback=>callback(),getComputedStyle:()=>({visibility:'visible'}),navigator:{clipboard:{writeText:async value=>copies.push(value)}},setTimeout:()=>1,clearTimeout:()=>{},window:{MotionPreview:{create(item){previews.push(item);const element=document.createElement('div');element.dataset.state='ready';element.destroy=()=>{};return element;}}}};
Object.assign(context,{URLSearchParams,location:{search:''}});
let source=fs.readFileSync(path.resolve(__dirname,'../dist/app.js'),'utf8');
const bindingMarker="  $('language-button').addEventListener";
assert.ok(source.includes(bindingMarker),'Frontend initialization boundary is present');
source=source.slice(0,source.indexOf(bindingMarker))+"  globalThis.variantTest={state,variants,originalRecords,selectedDetail,renderDetail,readerKey,meta,matches,navigateKeys,provenance,card};\n})();";
vm.runInNewContext(source,context,{filename:'app.js',timeout:1000});
const api=context.variantTest;
const palette=(id,title,colors,notice)=>({id,title,kind:'palette',category:'palette',language:'json',sourceName:'Actual upstream '+id,sourceUrl:'https://example.com/'+id,license:'MIT',licenseUrl:'https://example.com/'+id+'/license',licenseText:notice,colors,code:JSON.stringify(colors),analysis:{assetType:'palette',effects:[],components:['color'],useCases:['color-system'],techniques:['color-values'],preview:{renderer:'palette'}}});
const first=palette('palette-a','Original A',['#112233','#FFFFFF00'],'COMPLETE NOTICE A\nCopyright A');
const second=palette('palette-b','<script>Original B</script>',['#112244','#00000080'],'COMPLETE NOTICE B\nCopyright B');
const part=palette('old-component-id','Former component',['#445566'],'COMPONENT FULL NOTICE');
const family={...first,title:'Family title',code:'Canonical wrapper must not replace original code',aliases:[second.id,part.id],variants:[first,second,part],consolidation:{variantCount:2,variantRoles:{[part.id]:'component-part'}}};
Object.assign(api.state,{detail:family,detailVariant:first.id,detailTab:'overview'});
api.renderDetail(false);
let selector=document.getElementById('detail-variant-select');
assert.equal(selector.options.length,2,'Component parts are not offered as standalone previews');
assert.equal(selector.value,first.id,'The canonical original is the default');
assert.equal(selector.options[1].textContent,'2 / 2 · <script>Original B</script> · Actual upstream palette-b','Untrusted option text stays text');
assert.equal(previews.at(-1),first,'Preview receives the actual original record');
assert.equal(document.getElementById('detail-title').textContent,first.title);

api.state.detailTab='code';
api.renderDetail(false);
document.getElementById('detail-reader').scrollTop=123;
const firstReaderKey=api.readerKey();
selector=document.getElementById('detail-variant-select');selector.value=second.id;selector.dispatch('change');
assert.equal(api.selectedDetail(),second,'Selection changes to an exact retained original');
assert.notEqual(api.readerKey(),firstReaderKey,'Reader positions use the original variant identity');
const secondCode=JSON.parse(document.getElementById('detail-reader').textContent);
assert.deepEqual(secondCode.data,second.colors,'Color order and alpha values are unchanged');
assert.equal(secondCode.attribution.licenseText,second.licenseText,'Copyable code contains the selected source full notice');
assert.equal(secondCode.attribution.source,second.sourceUrl);
assert.equal(document.activeElement.id,'detail-variant-select','Selection restores keyboard focus');
assert.equal(family.code,'Canonical wrapper must not replace original code','Selection does not mutate the canonical record');
selector=document.getElementById('detail-variant-select');selector.value=first.id;selector.dispatch('change');
assert.equal(document.getElementById('detail-reader').scrollTop,123,'Returning to a variant restores its reader position');

selector=document.getElementById('detail-variant-select');selector.value=second.id;selector.dispatch('change');
api.state.detailTab='license';api.renderDetail(false);
assert.equal(document.getElementById('detail-reader').textContent,second.licenseText,'License tab shows the selected exact full notice');
const licenseCopy=document.getElementById('detail-content').querySelectorAll('button').find(button=>button.textContent==='라이선스 복사');
licenseCopy.dispatch('click');
assert.equal(copies.at(-1),second.licenseText,'License copy acts on the selected variant');
api.state.detailTab='overview';api.state.lang='en';api.renderDetail(false);
assert.equal(document.getElementById('detail-variant-select').value,second.id,'Language changes preserve selection');
assert.ok(document.getElementById('detail-variant-hint').textContent.startsWith('Original records'));
assert.equal(previews.at(-1),second,'Changing tabs or language keeps the actual preview');
const links=document.getElementById('detail-content').querySelectorAll('a');
assert.equal(links.find(link=>link.textContent==='Open original ↗').href,second.sourceUrl,'Original link follows the selected source');
assert.equal(links.find(link=>link.textContent==='Original license ↗').href,second.licenseUrl,'License link follows the selected source');

for(const key of ['ArrowUp','ArrowDown','Enter']){let prevented=false;api.navigateKeys({target:document.getElementById('detail-variant-select'),key,preventDefault(){prevented=true;}});assert.equal(prevented,false,`Native selector owns ${key}`);}
api.state.view='design';api.state.query=part.id;assert.equal(api.matches(family),true,'Merged component aliases remain discoverable in the design domain');
api.state.query='Original B';assert.equal(api.matches(family),true,'All original names remain searchable');
const provenance=JSON.parse(api.provenance(second));
assert.equal(provenance.mergedCollection.selectedVariantId,second.id);
assert.equal(provenance.mergedOriginals.length,3,'Every merged source remains accessible');
assert.equal(provenance.mergedOriginals[2].licenseText,part.licenseText);
assert.equal(provenance.mergedOriginals[2].variantRole,'component-part');
assert.equal(Object.hasOwn(provenance,'code'),false);

const repaired={...first,repair:{reason:'Original composition restored',originalRecord:{...first,code:'partial keyframes'}}};
api.state.detail={...repaired,variants:[first,part],consolidation:{variantRoles:{[part.id]:'component-part'}}};
api.state.detailVariant=first.id;
assert.equal(api.variants(api.state.detail).length,1,'Repair parts do not inflate meaningful variant count');
const repairedProvenance=JSON.parse(api.provenance(api.selectedDetail()));
assert.equal(repairedProvenance.repair.originalRecord.variantRole,'former-primary-record');
assert.equal(repairedProvenance.repair.originalRecord.licenseText,first.licenseText);
assert.equal(Object.hasOwn(repairedProvenance.repair.originalRecord,'code'),false,'Provenance does not repeat stored source code');
assert.equal(api.variants({...family,variants:Array.from({length:100},()=>first)}).length,64,'Variant rendering stays bounded');

// Check every real merged family and its retained originals in the generated
// catalog. The preview factory remains a stub: asset CSS/SVG/JS is never run.
const catalog=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../dist/catalog.json'),'utf8'));
const families=catalog.items.filter(item=>Array.isArray(item.variants)&&item.variants.length>1);
assert.ok(families.length>0,'Generated catalog contains actual merged records');
let actualVariants=0,actualAliases=0,repairedFamilies=0;
for(const merged of families){
  Object.assign(api.state,{detail:merged,detailVariant:merged.id,detailTab:'overview',query:'',lang:'en',view:api.meta(merged).domain});
  api.renderDetail(false);
  const selectable=api.variants(merged);
  const controls=document.getElementById('detail-content').querySelectorAll('select');
  assert.equal(controls.length,selectable.length>1?1:0,`Meaningful variant controls for ${merged.id}`);
  assert.equal(api.selectedDetail().id,merged.id,`Default original identity for ${merged.id}`);
  for(const alias of merged.aliases){api.state.query=alias;assert.equal(api.matches(merged),true,`Alias remains searchable: ${alias}`);actualAliases++;}
  for(const original of selectable){
    if(selectable.length>1){const choice=document.getElementById('detail-variant-select');choice.value=original.id;choice.dispatch('change');}
    assert.equal(api.selectedDetail(),original,`Actual retained original selected: ${original.id}`);
    assert.equal(previews.at(-1),original,`Exact record supplied to preview: ${original.id}`);
    api.state.detailTab='license';api.renderDetail(false);
    assert.equal(document.getElementById('detail-reader').textContent,original.licenseText,`Complete notice shown: ${original.id}`);
    api.state.detailTab='code';api.renderDetail(false);
    const originalCode=document.getElementById('detail-reader').textContent;
    if(original.kind==='palette'||original.language==='json'){
      const payload=JSON.parse(originalCode);
      assert.deepEqual(payload.data,JSON.parse(original.code),`Stored palette data and ordering preserved: ${original.id}`);
      assert.equal(payload.attribution.licenseText,original.licenseText);
    }else assert.ok(originalCode.endsWith(original.code),`Copyable source code preserved: ${original.id}`);
    api.state.detailTab='overview';api.renderDetail(false);actualVariants++;
  }
  if(merged.repair){
    repairedFamilies++;
    const selected=api.selectedDetail(),stored=JSON.parse(api.provenance(selected));
    assert.equal(stored.repair.originalRecord.licenseText,merged.repair.originalRecord.licenseText,`Parent repair notice projected: ${merged.id}`);
    assert.equal(Object.hasOwn(stored.repair.originalRecord,'code'),false);
    assert.deepEqual(selected.preview.dom,merged.preview.dom,`Repaired DOM is selected: ${merged.id}`);
  }
}

// Parse only the trusted DOM sanitizer prefix. This checks source DOM support
// and escaped markup without CSSOM, iframes, browsers, or imported execution.
let previewSource=fs.readFileSync(path.resolve(__dirname,'../dist/preview.js'),'utf8');
const cssMarker='  function sanitizedCss';
assert.ok(previewSource.includes(cssMarker));
previewSource=previewSource.slice(0,previewSource.indexOf(cssMarker))+"  globalThis.previewDomTest={safeTree,treeHtml,treeClasses};\n})();";
vm.runInNewContext(previewSource,context,{filename:'preview.js',timeout:1000});
for(const merged of families.filter(item=>item.repair)){
  const original=api.variants(merged).find(item=>item.id===merged.id),tree=context.previewDomTest.safeTree(original.preview.dom);
  assert.ok(tree,`Repaired source DOM sanitizes: ${merged.id}`);
  const originalClasses=new Set();
  function collect(raw){for(const name of (raw.className||'').split(' ').filter(Boolean))originalClasses.add(name);for(const child of raw.children||[])collect(child);}
  collect(original.preview.dom);
  const supported=context.previewDomTest.treeClasses(tree);
  assert.ok([...originalClasses].every(name=>supported.has(name)),`Every repaired component class is supported: ${merged.id}`);
  const markup=context.previewDomTest.treeHtml(tree);
  assert.ok(markup.startsWith('<div'),`Trusted DOM serialization succeeds: ${merged.id}`);
  assert.equal(/<script|on\w+=|src=|href=/i.test(markup),false);
}
queueMicrotask(()=>console.log(`Variant UI behavior checks passed: ${catalog.items.length} canonical records, ${families.length} families, ${actualVariants} selectable originals, ${actualAliases} aliases, ${repairedFamilies} repaired DOMs (DOM model; no browser rendering).`));
