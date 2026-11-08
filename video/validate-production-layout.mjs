/** Validate generated HTML on its real timeline before rendering an MP4. */
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {resolve,dirname} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {writeFileSync} from 'node:fs';
const require=createRequire(import.meta.url);
const puppeteer=require('puppeteer-core');
const video=dirname(fileURLToPath(import.meta.url)),work=resolve(process.argv[2]);
const cli=resolve(video,'node_modules/hyperframes/bin/hyperframes.mjs');
const chrome=execFileSync('node',[cli,'browser','path'],{encoding:'utf8'}).trim().split('\n').at(-1);
const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--allow-file-access-from-files']});
try{
 const page=await browser.newPage();
 await page.evaluateOnNewDocument(()=>{window.__timelines={};});
 await page.setViewport({width:1080,height:1920});
 await page.goto(pathToFileURL(resolve(work,'index.html')).href,{waitUntil:'load'});
 await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()));});
 const result=await page.evaluate(()=>{
  const root=document.querySelector('[data-composition-id]'),W=+(root?.dataset.width||1080),H=+(root?.dataset.height||1920);
  const clips=[...document.querySelectorAll('.clip')],timelines=Object.values(window.__timelines||{}),errors=[];
  if(!timelines.length)return {samples:0,errors:[{problem:'missing_timeline'}]};
  const times=new Set([1]);
  clips.forEach(c=>{let a=+c.dataset.start,d=+c.dataset.duration;if(Number.isFinite(a)&&d>0)times.add(a+Math.min(d/2,.85));});
  for(const scene of window.__qaScenes||[]) {times.add(scene.ini+.85);times.add((scene.ini+scene.fim)/2);}
  const rect=e=>e.getBoundingClientRect();
  const overlap=(a,b)=>a.left<b.right-2&&a.right>b.left+2&&a.top<b.bottom-2&&a.bottom>b.top+2;
  const visible=e=>{for(let n=e;n&&n!==document.body;n=n.parentElement){let s=getComputedStyle(n);if(s.display==='none'||s.visibility==='hidden'||+s.opacity<.05)return false;}return true;};
  for(const t of times){
   timelines.forEach(tl=>tl.seek(t,false));
   clips.forEach(c=>{let a=+c.dataset.start,d=+c.dataset.duration;if(!c.classList.contains('scene')&&Number.isFinite(a)&&d>0)c.style.visibility=t>=a&&t<a+d?'visible':'hidden';});
   const caps=[...document.querySelectorAll('.caps,.caption,.legenda')].filter(visible);
   if(caps.length>1)errors.push({t,problem:'duplicate_caption'});
   for(const panel of document.querySelectorAll('.panel[data-template="story_frame_image"],.story-frame-image')){
    if(!visible(panel))continue;
    const img=panel.querySelector('.art img,.story-art img'),title=panel.querySelector('h1,.rotulo');
    if(!img?.naturalWidth){errors.push({t,problem:'missing_image'});continue;}
    if(title&&overlap(rect(img),rect(title)))errors.push({t,problem:'image_title_overlap'});
    for(const c of caps)if(overlap(rect(img),rect(c)))errors.push({t,problem:'image_caption_overlap'});
   }
   for(const el of document.querySelectorAll('[data-qa-bounds],.qd-painel,.tv,.caption,.caps,.legenda')){
    if(!visible(el))continue;let b=rect(el);
    if(b.left< -2||b.top< -2||b.right>W+2||b.bottom>H+2)errors.push({t,problem:'out_of_frame',element:el.className});
    if(el.scrollWidth>el.clientWidth+3&&getComputedStyle(el).overflowX==='hidden')errors.push({t,problem:'clipped_text',element:el.className});
   }
  }
  return {samples:times.size,errors};
 });
 writeFileSync(resolve(work,'layout-check.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));if(result.errors.length)process.exitCode=1;
}finally{await browser.close();}
