'use strict';
// Copy these two QA files to dist/_phase2-design-qa.* for the local test host.
(async()=>{
  const output=document.getElementById('result'),samples=document.getElementById('samples');
  const report={total:0,ready:0,originalNodesPreserved:0,completeTagInventoriesPreserved:0,failures:[],examples:[],complete:false};
  try{
    const response=await fetch('/catalog.json',{cache:'no-store'});
    if(!response.ok)throw new Error('Canonical source catalog unavailable');
    const catalog=await response.json();
    const all=new URLSearchParams(location.search).get('all')==='1';
    const selected=all?catalog.items.filter(item=>item.id.startsWith('design-')&&item.language==='svg'):[];
    const byId=new Map(selected.map(item=>[item.id,item]));
    report.coverage=all?'all published design SVG records':'six representative published design SVG records';
    const selectors=all?selected.map(item=>[null,item.id]):[['cmocean','haline'],['Colorcet','glasbey'],['Hero Patterns','skulls'],['Coolshapes','flower-5'],['Wes Anderson','royal1'],['Tabler Icons','acorn']];
    for(const [provider,fragment] of selectors){
      const item=provider===null?byId.get(fragment):catalog.items.find(item=>item.sourceName===provider&&item.id.startsWith('design-')&&item.id.includes(fragment));
      if(!item){report.failures.push({provider,fragment,reason:'Published qualified source record missing'});continue;}
      const article=document.createElement('article'),heading=document.createElement('h2');heading.textContent=item.title;article.append(heading);
      const preview=MotionPreview.create(item,{compact:false,paused:true,lang:'en'});article.append(preview);if(report.total<6)samples.append(article);report.total++;
      const svg=preview.querySelector('svg');
      if(preview.dataset.state==='ready'&&svg)report.ready++;
      else report.failures.push({id:item.id,reason:preview.dataset.reason||'No inline original SVG renderer'});
      const original=new DOMParser().parseFromString(item.code,'image/svg+xml').documentElement;
      const expectedStops=original.querySelectorAll('stop').length,expectedRectangles=original.querySelectorAll('rect').length;
      const actualStops=svg?.querySelectorAll('stop').length??0,actualRectangles=svg?.querySelectorAll('rect').length??0;
      const countsPreserved=expectedStops===actualStops&&expectedRectangles===actualRectangles;
      if(countsPreserved)report.originalNodesPreserved++;
      else report.failures.push({id:item.id,reason:'Original authored sample nodes were dropped',expectedStops,actualStops,expectedRectangles,actualRectangles});
      const inventory=root=>{const counts={};if(root)for(const node of [root,...root.querySelectorAll('*')])counts[node.localName]=(counts[node.localName]||0)+1;return JSON.stringify(Object.entries(counts).sort(([a],[b])=>a.localeCompare(b)));};
      const completeInventoryPreserved=inventory(original)===inventory(svg);
      if(completeInventoryPreserved)report.completeTagInventoriesPreserved++;
      else report.failures.push({id:item.id,reason:'Full original SVG tag inventory changed',expected:inventory(original),actual:inventory(svg)});
      const originalColor=original.querySelector('stop')?.getAttribute('stop-color');
      const actualColor=svg?.querySelector('stop')?.getAttribute('stop-color');
      if(originalColor&&actualColor!==originalColor)report.failures.push({id:item.id,reason:'Original RGB percentage stop color changed'});
      if(!all||report.examples.length<6)report.examples.push({id:item.id,renderer:preview.dataset.renderer,state:preview.dataset.state,expectedStops,actualStops,expectedRectangles,actualRectangles,completeInventoryPreserved,firstStopPreserved:!originalColor||originalColor===actualColor});
      if(all&&report.total>6)preview.destroy();
    }
    report.complete=true;output.dataset.complete='true';output.textContent=JSON.stringify(report,null,2);
  }catch(error){output.dataset.complete='error';output.textContent=JSON.stringify({...report,error:String(error.message).slice(0,160)},null,2);}
})();
