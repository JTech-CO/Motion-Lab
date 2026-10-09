'use strict';
// Exercise trusted UI code without running collected CSS, SVG or JavaScript.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
class Element {
  constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.attributes={};this.events=new Map();this.dataset={};this.className='';this.classList={add(){},remove(){},contains(){return false;}};this._text='';this.open=false;this.isContentEditable=false;}
  set id(value){this._id=value;this.ownerDocument.ids.set(value,this);}get id(){return this._id||'';}
  set textContent(value){this._text=String(value);this.children=[];}get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  get isConnected(){return true;}
  append(...values){for(const value of values){if(value.tagName==='#FRAGMENT'){this.append(...value.children);continue;}value.parentElement=this;this.children.push(value);}}
  replaceChildren(...values){this.children=[];this._text='';this.append(...values);}
  setAttribute(name,value){this.attributes[name]=String(value);}getAttribute(name){return this.attributes[name]??null;}
  addEventListener(name,listener){if(!this.events.has(name))this.events.set(name,[]);this.events.get(name).push(listener);}
  dispatch(name,event={}){for(const listener of this.events.get(name)||[])listener({...event,target:this});}
  focus(){this.ownerDocument.activeElement=this;}
  matches(selector){return selector==='pre.code-block'&&this.tagName==='PRE'&&this.className==='code-block';}
  querySelectorAll(selector){const result=[];for(const child of this.children){if(selector==='button'&&child.tagName==='BUTTON'||selector==='a'&&child.tagName==='A'||selector==='pre'&&child.tagName==='PRE'||selector.startsWith('.')&&child.className.split(' ').includes(selector.slice(1)))result.push(child);result.push(...child.querySelectorAll(selector));}return result;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
}
class Select extends Element{}class Input extends Element{}class TextArea extends Element{}
const document={ids:new Map(),activeElement:null,createElement(tag){const Type=tag==='select'?Select:tag==='input'?Input:tag==='textarea'?TextArea:Element;return new Type(tag,this);},createDocumentFragment(){return new Element('#fragment',this);},getElementById(id){return this.ids.get(id)||null;}};
for(const id of ['detail-dialog','detail-content','detail-close','toast']){const element=document.createElement('div');element.id=id;}
document.getElementById('detail-dialog').open=true;
const previews=[],copies=[];
const context={document,HTMLElement:Element,HTMLSelectElement:Select,HTMLInputElement:Input,HTMLTextAreaElement:TextArea,URL,URLSearchParams,location:{search:''},WeakMap,Map,Set,Promise,JSON,Object,Array,String,Number,Boolean,Math,matchMedia:()=>({matches:false}),requestAnimationFrame:callback=>callback(),navigator:{clipboard:{writeText:async value=>copies.push(value)}},setTimeout:()=>1,clearTimeout:()=>{},window:{MotionPreview:{create(item,options){previews.push({item,options});const element=document.createElement('div');element.dataset.state='ready';element.destroy=()=>{};element.setPaused=()=>{};if(options.reference){const caption=document.createElement('span');caption.className='motion-preview-reference-label';caption.textContent='Renderer default';element.append(caption);}return element;}}}};
let source=fs.readFileSync(path.resolve(__dirname,'../dist/app.js'),'utf8');
const marker="  $('language-button').addEventListener";assert.ok(source.includes(marker));
source=source.slice(0,source.indexOf(marker))+"  globalThis.referenceTest={state,meta,matches,referenceLocal,createPreview,previewCodeText,renderDetail};\n})();";
vm.runInNewContext(source,context,{filename:'app.js',timeout:1000});
const api=context.referenceTest;
const asset={id:'actual-motion',title:'Actual source asset',kind:'code',category:'animation',language:'css',code:'.motion-sample{animation:real 2s infinite}@keyframes real{to{opacity:0}}',license:'MIT',licenseText:'COMPLETE UPSTREAM NOTICE',sourceUrl:'https://example.com/asset',licenseUrl:'https://example.com/license',analysis:{domain:'motion',assetType:'animation',effects:['fade'],components:['shape'],useCases:['attention'],preview:{renderer:'css'}}};
const base={id:'reference-original',title:'<script>Original title</script>',kind:'reference',category:'reference',language:'url',code:null,license:'Original terms not stated',licenseText:null,sourceUrl:'https://example.com/reference',analysis:{domain:null,assetType:'reference',preview:{renderer:'none'}}};
const review={targetDomain:'tooling',resourceType:'tool',assetType:'interaction',effects:['spring'],components:['shape'],useCases:['design-kit'],evidence:{basis:'reviewed-source',confidence:'medium',summaryKO:'도구의 원문을 검토했습니다.',summaryEN:'Reviewed source text.',signals:['reviewed tool']}};
const related={...base,referenceReview:{...review,preview:{mode:'related-asset',assetId:asset.id,limitations:['Local example does not reproduce the referenced product.']}}};
const illustration={...base,id:'reference-illustration',referenceReview:{...review,targetDomain:'design',resourceType:'example',assetType:'pattern',effects:['pixel'],preview:{mode:'illustration',language:'svg',code:'<svg viewBox="0 0 80 80"><rect width="80" height="80" fill="#71e3ed"/></svg>',license:'CC0-1.0',notice:'Motion Lab concept illustration dedicated under CC0 1.0.',attribution:'Motion Lab',limitations:['Conceptual illustration only.']}}};
api.state.items=[asset,related,illustration];
api.state.view='references';
const snapshot=JSON.stringify(related);
assert.equal(api.meta(related).referenceDomain,'tooling');assert.equal(api.meta(related).assetType,'interaction');
assert.equal(api.meta(related).effects[0],'spring');assert.equal(related.category,'reference');
api.state.filters.referenceDomain.add('design');assert.equal(api.matches(illustration),true);assert.equal(api.matches(related),false);api.state.filters.referenceDomain.clear();
assert.equal(api.meta(related).resourceType,'tool');api.state.filters.resourceType.add('example');assert.equal(api.matches(illustration),true);assert.equal(api.matches(related),false);api.state.filters.resourceType.clear();api.state.query='개별 예시';assert.equal(api.matches(illustration),true);assert.equal(api.matches(related),false);api.state.query='';
api.state.query='제작 도구';assert.equal(api.matches(related),true);assert.equal(api.matches(illustration),false);api.state.query='';
api.state.query='도구의 원문';assert.equal(api.matches(related),true);api.state.query='reviewed source text';assert.equal(api.matches(related),true);api.state.query='';
api.createPreview(related,true);assert.equal(previews.at(-1).item,asset);assert.equal(previews.at(-1).options.reference.mode,'related-asset');assert.equal(previews.at(-1).options.reference.id,related.id);
Object.assign(api.state,{detail:related,detailVariant:related.id,detailTab:'overview'});api.renderDetail(false);
assert.ok(document.getElementById('detail-content').textContent.includes('관련 로컬 에셋'));
assert.ok(document.getElementById('detail-content').textContent.includes('원본 사이트의 화면이나 원본 소스가 아닙니다'));
assert.ok(document.getElementById('detail-content').querySelectorAll('a').some(link=>link.href===asset.sourceUrl&&link.textContent==='미리보기 에셋 출처 ↗'));
assert.ok(document.getElementById('detail-content').querySelectorAll('a').some(link=>link.href===related.sourceUrl&&link.textContent==='원본 열기 ↗'));
assert.ok(document.getElementById('detail-content').querySelectorAll('button').some(button=>button.textContent==='모션 정지'));
assert.ok(!document.getElementById('detail-content').querySelectorAll('button').some(button=>button.textContent==='코드 복사'));
assert.equal(document.getElementById('detail-title').textContent,related.title);
assert.equal(JSON.stringify(related),snapshot,'Rendering does not mutate source reference fields');
api.state.detailTab='license';api.renderDetail(false);
assert.ok(document.getElementById('detail-content').textContent.includes('원본 참고 자료 이용 조건'));
assert.ok(document.getElementById('detail-content').textContent.includes(asset.licenseText));
const relatedButton=document.getElementById('detail-content').querySelectorAll('button').find(button=>button.textContent==='미리보기 라이선스 복사');relatedButton.dispatch('click');assert.equal(copies.at(-1),asset.licenseText);
const illustrationPreview=api.createPreview(illustration,false);assert.equal(previews.at(-1).item.kind,'code');assert.equal(previews.at(-1).item.code,illustration.referenceReview.preview.code);assert.equal(previews.at(-1).item.analysis.domain,'design');assert.equal(illustrationPreview.querySelector('.motion-preview-reference-label').textContent,'Motion Lab 개념도');
Object.assign(api.state,{detail:illustration,detailVariant:illustration.id,detailTab:'previewCode'});api.renderDetail(false);
assert.ok(document.getElementById('detail-content').textContent.includes('참고 자료의 원본 코드가 아닙니다'));
assert.ok(document.getElementById('detail-reader').textContent.includes(illustration.referenceReview.preview.notice));
assert.ok(document.getElementById('detail-reader').textContent.includes('This is not source code from the reference.'));
assert.ok(document.getElementById('detail-reader').textContent.endsWith(illustration.referenceReview.preview.code));
assert.equal(illustration.code,null);assert.equal(illustration.license,base.license);
api.state.detailTab='overview';api.renderDetail(false);assert.ok(!document.getElementById('detail-content').querySelectorAll('button').some(button=>button.textContent==='모션 정지'));
api.state.lang='en';api.renderDetail(false);assert.ok(document.getElementById('detail-content').textContent.includes('Motion Lab illustration'));assert.ok(document.getElementById('detail-content').querySelectorAll('.motion-preview-reference-label').some(node=>node.textContent==='Motion Lab illustration'));
const unavailable={...illustration,id:'unavailable-reference',referenceReview:{...illustration.referenceReview,evidence:{basis:'metadata',confidence:'low',status:'source-unavailable',summaryEN:'The source video cannot be verified.'}}};
Object.assign(api.state,{detail:unavailable,detailVariant:unavailable.id,detailTab:'overview'});api.renderDetail(false);assert.ok(document.getElementById('detail-content').textContent.includes('Only a general concept illustration is provided'));assert.ok(document.getElementById('detail-content').textContent.includes('Source content unavailable'));
for(const preview of [
  {mode:'related-asset',assetId:related.id},{mode:'related-asset',assetId:'missing'},
  {...illustration.referenceReview.preview,mode:'source'},
  {...illustration.referenceReview.preview,language:'html'},
  {...illustration.referenceReview.preview,code:'x'.repeat(200001)},
  {...illustration.referenceReview.preview,notice:''},
  {...illustration.referenceReview.preview,attribution:'Someone else'},
  {...illustration.referenceReview.preview,license:'MIT'}
])assert.equal(api.referenceLocal({...related,referenceReview:{...review,preview}}),null);
const catalog=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../dist/catalog.json'),'utf8'));
const references=catalog.items.filter(item=>item.kind==='reference');
let actual=0;
if(references.some(item=>item.referenceReview)){
  api.state.items=catalog.items;
  for(const item of references){
    const before=JSON.stringify(item),local=api.referenceLocal(item);assert.ok(local,'Every reviewed reference has an allowed local preview: '+item.id);
    assert.ok(['motion','design','mixed','tooling'].includes(api.meta(item).referenceDomain));
    assert.ok(['example','library','tool','design-system','case-study','collection','learning','portfolio'].includes(api.meta(item).resourceType));
    Object.assign(api.state,{detail:item,detailVariant:item.id,detailTab:'overview'});api.renderDetail(false);
    assert.equal(previews.at(-1).item.code,local.asset.code);assert.equal(previews.at(-1).options.reference.id,item.id);
    assert.equal(JSON.stringify(item),before);actual++;
  }
}
console.log('Reference UI checks passed: classification/filtering, exact local resolver, separate original and preview rights, bounded modes, '+actual+' actual reviewed references (DOM model; no collected code execution).');
