const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', 'static');
const MIME = {
  '.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.json':'application/json',
  '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp',
  '.ico':'image/x-icon','.txt':'text/plain; charset=utf-8'
};
function assert(condition,message){if(!condition)throw new Error(message);}
function startServer(){
  return new Promise(resolve=>{
    const server=http.createServer((req,res)=>{
      let pathname;
      try{pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);}catch{res.writeHead(400).end('Bad request');return;}
      if(pathname==='/')pathname='/index.html';
      if(pathname.endsWith('/'))pathname+='index.html';
      const target=path.resolve(ROOT,'.'+pathname);
      if(!target.startsWith(ROOT+path.sep)&&target!==path.join(ROOT,'index.html')){res.writeHead(403).end('Forbidden');return;}
      fs.readFile(target,(err,data)=>{
        if(err){res.writeHead(404).end('Not found');return;}
        res.writeHead(200,{'content-type':MIME[path.extname(target).toLowerCase()]||'application/octet-stream','cache-control':'no-store'});
        res.end(data);
      });
    });
    server.listen(0,'127.0.0.1',()=>resolve({server,base:'http://127.0.0.1:'+server.address().port}));
  });
}
async function makePdf(page,pages){
  const base64=await page.evaluate(async n=>{
    const doc=await window.PDFLib.PDFDocument.create();
    for(let i=1;i<=n;i++){
      const p=doc.addPage([360,240]);
      p.drawText('PDF Globe browser smoke page '+i,{x:30,y:190,size:18});
      p.drawText('Generated locally in Chromium',{x:30,y:155,size:11});
    }
    const bytes=await doc.save();let binary='';
    for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
    return btoa(binary);
  },pages);
  return Buffer.from(base64,'base64');
}
async function makePng(page){
  const base64=await page.evaluate(()=>{
    const c=document.createElement('canvas');c.width=720;c.height=240;
    const x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height);
    x.fillStyle='#111';x.font='bold 64px Arial';x.fillText('PDF Globe OCR Test',26,112);
    x.font='32px Arial';x.fillText('Image for print tools',28,176);
    return c.toDataURL('image/png').split(',')[1];
  });
  return Buffer.from(base64,'base64');
}
async function readPdfResult(page){
  await page.waitForFunction(()=>{
    const box=document.querySelector('#resultBox');
    return box&&!box.classList.contains('hidden')&&box.querySelector('a.download-link');
  },null,{timeout:60000});
  return page.locator('#resultBox a.download-link').evaluate(async link=>{
    const response=await fetch(link.href);const bytes=new Uint8Array(await response.arrayBuffer());
    const pdf=await window.PDFLib.PDFDocument.load(bytes);
    return {filename:link.download,size:bytes.length,pages:pdf.getPageCount(),header:String.fromCharCode(...bytes.slice(0,5))};
  });
}
async function runPdfTool(page,base,tool,files,configure,expectedPages){
  await page.goto(base+'/?tool='+encodeURIComponent(tool),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PDFLib&&!!document.querySelector('#workspaceSection.visible'),null,{timeout:60000});
  if(configure)await configure(page);
  await page.locator('#fileInput').setInputFiles(files);
  await page.locator('#runTool').click();
  const result=await readPdfResult(page);
  assert(result.header==='%PDF-',tool+': output is not a PDF');
  assert(result.pages===expectedPages,tool+': expected '+expectedPages+' pages, received '+result.pages);
  assert(result.size>250,tool+': output PDF is unexpectedly small');
  console.log('PASS browser PDF tool '+tool+': '+result.pages+' page(s), '+result.size+' bytes');
}
async function runPdfToImages(page,base,pdf){
  await page.goto(base+'/?tool=pdf-image',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PDFLib&&!!window.pdfjsLib&&!!window.JSZip&&!!document.querySelector('#workspaceSection.visible'),null,{timeout:60000});
  await page.locator('#fileInput').setInputFiles({name:'browser-sample.pdf',mimeType:'application/pdf',buffer:pdf});
  await page.locator('#runTool').click();
  await page.waitForFunction(()=>{
    const a=document.querySelector('#resultBox a.download-link');
    return a&&!document.querySelector('#resultBox').classList.contains('hidden');
  },null,{timeout:60000});
  const result=await page.locator('#resultBox a.download-link').evaluate(async a=>{
    const res=await fetch(a.href);const b=new Uint8Array(await res.arrayBuffer());
    return {filename:a.download,size:b.length,zip:b[0]===0x50&&b[1]===0x4b};
  });
  assert(result.zip&&result.size>100,'PDF to images did not create a valid ZIP: '+JSON.stringify(result));
  console.log('PASS browser PDF-to-images: '+result.filename+', '+result.size+' bytes');
}
async function runOcr(page,base,png){
  await page.goto(base+'/?tool=ocr',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.Tesseract&&!!document.querySelector('#workspaceSection.visible'),null,{timeout:60000});
  await page.locator('#ocrLang').fill('eng');
  await page.locator('#fileInput').setInputFiles({name:'ocr-test.png',mimeType:'image/png',buffer:png});
  await page.locator('#runTool').click();
  await page.waitForFunction(()=>{
    const a=document.querySelector('#resultBox a.download-link');
    return a&&!document.querySelector('#resultBox').classList.contains('hidden');
  },null,{timeout:180000});
  const text=await page.locator('#resultBox a.download-link').evaluate(async a=>await (await fetch(a.href)).text());
  assert(text.length>0,'OCR returned an empty text file');
  console.log('PASS browser OCR: '+text.length+' characters extracted');
}
async function runSaffha(page,base,png){
  await page.goto(base+'/saffha/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PDFLib&&!!document.querySelector('#downloadBtn'),null,{timeout:60000});
  await page.locator('#fileInput').setInputFiles({name:'saffha-sample.png',mimeType:'image/png',buffer:png});
  await page.waitForFunction(()=>!document.querySelector('#downloadBtn').disabled,null,{timeout:30000});
  const downloadPromise=page.waitForEvent('download',{timeout:60000});
  await page.locator('#downloadBtn').click();
  const download=await downloadPromise;const file=await download.path();const bytes=fs.readFileSync(file);
  assert(bytes.subarray(0,5).toString()==='%PDF-','Saffha did not generate a PDF');
  assert(bytes.length>500,'Saffha PDF output is unexpectedly small');
  console.log('PASS Saffha PDF: '+download.suggestedFilename()+', '+bytes.length+' bytes');
}
async function runPoster(page,base,png){
  const pageErrors=[];
  page.on('pageerror',error=>pageErrors.push(error.message));
  await page.goto(base+'/poster-splitter.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PDFLib&&document.documentElement.dataset.posterReady==='true'&&!!document.querySelector('#generateBtn'),null,{timeout:60000});
  await page.locator('#posterSize').selectOption('A4');
  await page.locator('#fileInput').setInputFiles({name:'poster-sample.png',mimeType:'image/png',buffer:png});
  await page.waitForTimeout(1200);
  const state=await page.evaluate(()=>({
    enabled:!document.querySelector('#generateBtn').disabled,
    status:document.querySelector('#statusBox').textContent,
    statusClass:document.querySelector('#statusBox').className,
    fileRow:document.querySelector('#fileRow').className,
    filename:document.querySelector('#fileName').textContent,
    hasPdfLib:!!window.PDFLib
  }));
  if(!state.enabled)throw new Error('Poster Splitter did not enable generation: '+JSON.stringify(state)+'; page errors: '+pageErrors.join(' | '));
  await page.locator('#generateBtn').click();
  await page.waitForFunction(()=>document.querySelector('#downloadBtn').classList.contains('show'),null,{timeout:90000});
  const downloadPromise=page.waitForEvent('download',{timeout:60000});
  await page.locator('#downloadBtn').click();
  const download=await downloadPromise;const file=await download.path();const bytes=fs.readFileSync(file);
  assert(bytes.subarray(0,5).toString()==='%PDF-','Poster splitter did not generate a PDF');
  assert(bytes.length>500,'Poster splitter PDF output is unexpectedly small');
  console.log('PASS Poster Splitter PDF: '+download.suggestedFilename()+', '+bytes.length+' bytes');
}

async function runUnitConverter(page,base){
  await page.goto(base+'/unit-converter.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelectorAll('#category option').length>=10,null,{timeout:30000});
  await page.locator('#category').selectOption('length');
  await page.locator('#amount').fill('2');
  await page.locator('#fromUnit').selectOption('m');
  await page.locator('#toUnit').selectOption('cm');
  const result=await page.locator('#resultFormula').textContent();
  const normalized=result.replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
  assert(normalized.includes('200')&&normalized.includes('cm'),'Unit converter result is unexpected: '+result);
  await page.locator('#originalServings').fill('4');
  await page.locator('#targetServings').fill('8');
  const factor=await page.locator('#scaleFactor').textContent();
  assert(factor.includes('2'),'Recipe calculator did not double servings');
  console.log('PASS unit converter: 2 m = 200 cm; recipe scaling 4 to 8 servings');
}
async function runImageModes(page,base){
  const modes=[
    {mode:'convert',visible:['outputFormat','quality'],hidden:['width','sharpen']},
    {mode:'resize',visible:['outputFormat','width','height','keepAspect'],hidden:['sharpen']},
    {mode:'compress',visible:['outputFormat','quality'],hidden:['width','sharpen']},
    {mode:'enhance',visible:['outputFormat','sharpen','contrast','brightness'],hidden:['width','height']}
  ];
  for(const item of modes){
    await page.goto(base+'/image-compressor.html?mode='+item.mode,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>!!document.querySelector('#compressImages'),null,{timeout:30000});
    for(const id of item.visible)assert(await page.locator('#'+id).evaluate(el=>!el.closest('.field').hidden),item.mode+': '+id+' should be visible');
    for(const id of item.hidden)assert(await page.locator('#'+id).evaluate(el=>el.closest('.field').hidden),item.mode+': '+id+' should be hidden');
  }
  console.log('PASS image modes: conversion, resize, compression and enhancement controls');
}
(async()=>{
  const serverInfo=await startServer();const server=serverInfo.server;const base=serverInfo.base;let browser;
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    const context=await browser.newContext({acceptDownloads:true,ignoreHTTPSErrors:true});
    await context.route('https://pdf-globe.onrender.com/**',async route=>{
      const url=new URL(route.request().url());
      if(url.pathname==='/api/health')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,translation_provider:'MyMemory',libreoffice:true,qpdf:true,capabilities:{}})});
      if(url.pathname==='/api/languages')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({languages:[]})});
      return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Browser smoke test blocks live API writes'})});
    });
    const page=await context.newPage();page.setDefaultTimeout(60000);
    await page.goto(base+'/',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>!!window.PDFLib,null,{timeout:60000});
    const pdf=await makePdf(page,2);const png=await makePng(page);
    const single={name:'one-page.pdf',mimeType:'application/pdf',buffer:await makePdf(page,1)};
    const two={name:'two-pages.pdf',mimeType:'application/pdf',buffer:pdf};
    await runPdfTool(page,base,'merge',[single,{...single,name:'two.pdf'}],null,2);
    await runPdfTool(page,base,'split',[two],p=>p.locator('#pageSpec').fill('2'),1);
    await runPdfTool(page,base,'delete',[two],p=>p.locator('#pageSpec').fill('2'),1);
    await runPdfTool(page,base,'rotate',[two],null,2);
    await runPdfTool(page,base,'reorder',[two],p=>p.locator('#pageOrder').fill('2,1'),2);
    await runPdfTool(page,base,'watermark',[two],p=>p.locator('#watermarkText').fill('PDF GLOBE TEST'),2);
    await runPdfTool(page,base,'numbers',[two],null,2);
    await runPdfTool(page,base,'sign',[two],async p=>{
      await p.locator('#signaturePad').scrollIntoViewIfNeeded();
      const box=await p.locator('#signaturePad').boundingBox();assert(!!box,'Signature canvas is not visible');
      await p.mouse.move(box.x+25,box.y+30);await p.mouse.down();
      await p.mouse.move(box.x+100,box.y+80,{steps:6});await p.mouse.up();
    },2);
    await runPdfToImages(page,base,two.buffer);
    await runOcr(page,base,png);
    await runSaffha(page,base,png);
    await runPoster(page,base,png);
    await runUnitConverter(page,base);
    await runImageModes(page,base);
    console.log('PASS ALL BROWSER SMOKE TESTS: client-side PDF, OCR, print, unit and image tools');
    await context.close();
  }catch(error){
    console.error(error&&error.stack?error.stack:error);process.exitCode=1;
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})();
