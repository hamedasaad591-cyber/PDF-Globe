(() => {
'use strict';
const $=id=>document.getElementById(id);
const TXT={
ar:{home:'الرئيسية',pdfTools:'أدوات PDF',unitTool:'محول الوحدات',eyebrow:'مجانية — معالجة محلية',heading:'ضغط الصور وتغيير حجمها',intro:'قلّل حجم صورك أو غيّر أبعادها مع التحكم في الجودة والصيغة. مناسبة للمواقع والمشاركة والطباعة.',tag1:'لا حاجة للتسجيل',tag2:'صورك لا تغادر جهازك',tag3:'JPG · PNG · WebP',dropTitle:'اسحب الصور إلى هنا',dropText:'أو اختر صوراً من جهازك — يمكنك تحديد عدة صور',choose:'اختيار الصور',limits:'JPG أو PNG أو WebP · حتى 25 MB للصورة · 20 صورة في المرة',format:'صيغة الإخراج',maxDimension:'أقصى بُعد للصورة',original:'الحجم الأصلي',quality:'جودة الإخراج',background:'خلفية الصور الشفافة عند التحويل إلى JPG',compress:'ضغط الصور الآن',waiting:'اختر الصور لتبدأ.',resultsTitle:'الصور بعد المعالجة',downloadAll:'تنزيل كل النتائج',privacyNote:'خصوصيتك: تتم المعالجة داخل متصفحك باستخدام Canvas. لا يتم إرسال الصور إلى PDF Globe أو أي خادم.',info1Title:'ضغط الصور',info1Text:'قلّل حجم ملفات الصور لتسهيل رفعها ومشاركتها وتسريع صفحات الويب.',info2Title:'تغيير الأبعاد',info2Text:'حدد أقصى عرض أو ارتفاع مع الحفاظ على نسبة أبعاد الصورة.',info3Title:'اختيار الصيغة',info3Text:'حوّل الصور إلى WebP أو JPG أو PNG بحسب احتياجك.',faqTitle:'أسئلة شائعة',faq1q:'هل يتم رفع صوري إلى الإنترنت؟',faq1a:'لا. تتم المعالجة على جهازك داخل المتصفح، ولا يتم رفع الصور إلى الخادم.',faq2q:'أي صيغة أختار؟',faq2a:'WebP غالباً يعطي حجماً أصغر للويب. JPG مناسب للصور الفوتوغرافية، وPNG مناسب للرسومات التي تحتاج إلى شفافية أو حواف دقيقة.',faq3q:'هل يؤثر الضغط في جودة الصورة؟',faq3a:'ضغط JPG وWebP قد يقلل بعض التفاصيل بحسب الجودة المختارة. احتفظ بالأصل عند الحاجة إلى أعلى جودة.',backHome:'← العودة إلى PDF Globe',privacy:'الخصوصية',terms:'الشروط',selected:'صور محددة',ready:'جاهز للمعالجة',settingsChanged:'تم تغيير الإعدادات. أعد الضغط لتحديث النتائج.',pngQuality:'صيغة PNG لا تستخدم شريط الجودة لأنها صيغة غير فقدية.',processing:'جارٍ ضغط الصور...',done:'اكتملت معالجة الصور.',failed:'تعذرت معالجة هذه الصورة',unsupported:'صيغة غير مدعومة. اختر JPG أو PNG أو WebP.',tooBig:'يتجاوز الملف حد 25 MB.',tooMany:'يمكن معالجة 20 صورة كحد أقصى في المرة.',originalSize:'الأصل',newSize:'النتيجة',saved:'تم توفير',noSavings:'الحجم الناتج أكبر من الأصل',download:'تنزيل',allDone:'تم تجهيز',copied:'',batchReady:'تم تجهيز الملفات للتنزيل.'},
en:{home:'Home',pdfTools:'PDF tools',unitTool:'Unit converter',eyebrow:'Free — local processing',heading:'Compress & Resize Images',intro:'Reduce image file sizes or resize dimensions with control over quality and format. Useful for websites, sharing and print.',tag1:'No sign-up required',tag2:'Images stay on your device',tag3:'JPG · PNG · WebP',dropTitle:'Drop images here',dropText:'Or choose images from your device — multiple files supported',choose:'Choose images',limits:'JPG, PNG or WebP · up to 25 MB per image · 20 images per batch',format:'Output format',maxDimension:'Maximum image dimension',original:'Original size',quality:'Output quality',background:'Background for transparent images converted to JPG',compress:'Compress images',waiting:'Choose images to begin.',resultsTitle:'Processed images',downloadAll:'Download all results',privacyNote:'Privacy: processing happens locally in your browser using Canvas. Images are not sent to PDF Globe or any server.',info1Title:'Compress images',info1Text:'Reduce image file sizes to make uploads and sharing easier and speed up web pages.',info2Title:'Resize dimensions',info2Text:'Set a maximum width or height while preserving the image aspect ratio.',info3Title:'Choose a format',info3Text:'Convert images to WebP, JPG or PNG for your needs.',faqTitle:'Frequently asked questions',faq1q:'Are my images uploaded?',faq1a:'No. Processing happens on your device in the browser. Images are not uploaded to a server.',faq2q:'Which format should I choose?',faq2a:'WebP often produces smaller web images. JPG is suitable for photographs, while PNG is useful for graphics that need transparency or crisp edges.',faq3q:'Does compression affect image quality?',faq3a:'JPG and WebP compression may reduce some details depending on the chosen quality. Keep the original when you need maximum quality.',backHome:'← Back to PDF Globe',privacy:'Privacy',terms:'Terms',selected:'selected images',ready:'Ready to process',settingsChanged:'Settings changed. Compress again to refresh the results.',pngQuality:'PNG is lossless, so the quality slider does not apply.',processing:'Compressing images...',done:'Image processing complete.',failed:'Could not process this image',unsupported:'Unsupported format. Choose JPG, PNG or WebP.',tooBig:'File exceeds the 25 MB limit.',tooMany:'You can process up to 20 images per batch.',originalSize:'Original',newSize:'Result',saved:'Saved',noSavings:'Output file is larger than the original',download:'Download',allDone:'Prepared',batchReady:'Files are ready to download.'}
};
let lang=document.documentElement.lang==='en'?'en':'ar',files=[],outputs=[];
function t(k){return TXT[lang][k]||TXT.en[k]||k}
function text(el,key){el.textContent=t(key)}
function setLanguage(){
 document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';$('pageLanguage').value=lang;
 document.querySelectorAll('[data-t]').forEach(el=>text(el,el.dataset.t));
 $('qualityValue').textContent=$('quality').value+'%';
 if(files.length)renderSelected();
}
function formatSize(bytes){
 if(bytes<1024)return bytes+' B';
 if(bytes<1048576)return (bytes/1024).toFixed(1)+' KB';
 return (bytes/1048576).toFixed(2)+' MB';
}
function setStatus(s){$('status').textContent=s}
function refreshQualityControl(){
 const lossless=$('outputFormat').value==='png';
 $('quality').disabled=lossless;
 $('qualityValue').textContent=$('quality').value+'%';
 $('qualityValue').title=lossless?t('pngQuality'):'';
}
function invalidateResults(){
 if(!outputs.length)return;
 outputs.forEach(o=>URL.revokeObjectURL(o.url));outputs=[];
 $('results').hidden=true;
 setStatus(t('settingsChanged'));
}
function supported(f){return ['image/jpeg','image/png','image/webp'].includes(f.type)||/\.(jpe?g|png|webp)$/i.test(f.name)}
function setFiles(incoming){
 const next=[...incoming];
 if(next.length>20){setStatus(t('tooMany'));return}
 const invalid=next.find(f=>!supported(f));
 if(invalid){setStatus(t('unsupported'));return}
 const oversized=next.find(f=>f.size>25*1024*1024);
 if(oversized){setStatus(t('tooBig'));return}
 files=next;outputs.forEach(o=>URL.revokeObjectURL(o.url));outputs=[];
 $('results').hidden=true;$('compressImages').disabled=!files.length;
 renderSelected();
 setStatus(files.length+' '+t('selected')+' · '+t('ready'));
}
function renderSelected(){
 const box=$('selectedFiles');box.innerHTML='';
 if(!files.length){box.hidden=true;return}
 box.hidden=false;
 files.forEach(f=>{const chip=document.createElement('span');chip.className='file-chip';chip.textContent=f.name+' · '+formatSize(f.size);box.appendChild(chip)});
}
async function loadBitmap(file){
 if('createImageBitmap' in window)return await createImageBitmap(file);
 const url=URL.createObjectURL(file);
 try{return await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=url})}
 finally{URL.revokeObjectURL(url)}
}
function blobFromCanvas(canvas,mime,quality){return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Canvas export failed')),mime,quality))}
async function processOne(file){
 const bitmap=await loadBitmap(file),w=bitmap.width||bitmap.naturalWidth,h=bitmap.height||bitmap.naturalHeight;
 if(!w||!h)throw new Error(t('failed'));
 const max=Number($('maxDimension').value)||0,scale=max?Math.min(1,max/Math.max(w,h)):1;
 const width=Math.max(1,Math.round(w*scale)),height=Math.max(1,Math.round(h*scale));
 const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
 const ctx=canvas.getContext('2d',{alpha:true});
 const fmt=$('outputFormat').value,mime=fmt==='jpeg'?'image/jpeg':fmt==='png'?'image/png':'image/webp';
 if(fmt==='jpeg'){ctx.fillStyle=$('background').value||'#ffffff';ctx.fillRect(0,0,width,height)}
 ctx.drawImage(bitmap,0,0,width,height);
 if(typeof bitmap.close==='function')bitmap.close();
 const q=Number($('quality').value)/100;
 let blob=await blobFromCanvas(canvas,mime,fmt==='png'?undefined:q);
 // Some browsers may not support WebP encoding; fall back to PNG rather than mislabel an output.
 let extension=fmt==='jpeg'?'jpg':fmt;
 if(fmt==='webp'&&blob.type!=='image/webp'){blob=await blobFromCanvas(canvas,'image/png');extension='png'}
 const base=file.name.replace(/\.[^.]+$/,'');
 const outputName=base+'_compressed.'+extension;
 const url=URL.createObjectURL(blob);
 return {name:file.name,outputName,url,blob,original:file.size,width,height,oldWidth:w,oldHeight:h,mime:blob.type};
}
function renderResults(){
 const grid=$('resultGrid');grid.innerHTML='';
 outputs.forEach(o=>{
  const card=document.createElement('article');card.className='result-card';
  const img=document.createElement('img');img.src=o.url;img.alt=o.outputName;
  const info=document.createElement('div');info.className='result-info';
  const title=document.createElement('strong');title.textContent=o.outputName;
  const detail=document.createElement('small');detail.textContent=o.oldWidth+'×'+o.oldHeight+' → '+o.width+'×'+o.height+' · '+formatSize(o.original)+' → '+formatSize(o.blob.size);
  const status=document.createElement('small');
  if(o.blob.size<o.original){const pct=(100-(o.blob.size/o.original*100)).toFixed(1);status.textContent=t('saved')+' '+pct+'%';status.style.color='#269d7a'}
  else{status.textContent=t('noSavings');status.style.color='#b77843'}
  const link=document.createElement('a');link.href=o.url;link.download=o.outputName;link.textContent=t('download');
  info.append(title,detail,status,link);card.append(img,info);grid.appendChild(card);
 });
 $('results').hidden=!outputs.length;
}
async function run(){
 if(!files.length)return;
 $('compressImages').disabled=true;outputs.forEach(o=>URL.revokeObjectURL(o.url));outputs=[];
 setStatus(t('processing'));
 const failures=[];
 for(let i=0;i<files.length;i++){
  try{outputs.push(await processOne(files[i]));setStatus((i+1)+' / '+files.length+' · '+t('processing'))}
  catch(e){failures.push(files[i].name+': '+(e.message||t('failed')))}
 }
 renderResults();$('compressImages').disabled=false;
 setStatus(failures.length?t('done')+' '+failures.length+' '+t('failed'):(t('done')+' '+outputs.length));
 if(failures.length)alert(failures.join('\n'));
}
$('pageLanguage').addEventListener('change',e=>{
 const english=window.location.pathname.startsWith('/en/');
 if(e.target.value==='en'&&!english){window.location.assign('/en/image-compressor.html');return}
 if(e.target.value==='ar'&&english){window.location.assign('/image-compressor.html');return}
 lang=e.target.value;setLanguage();
});
$('chooseImages').addEventListener('click',e=>{e.stopPropagation();$('imageInput').click()});
$('dropZone').addEventListener('click',e=>{if(e.target.closest('button'))return;$('imageInput').click()});
$('dropZone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('imageInput').click()}});
['dragenter','dragover'].forEach(ev=>$('dropZone').addEventListener(ev,e=>{e.preventDefault();$('dropZone').classList.add('dragover')}));
['dragleave','drop'].forEach(ev=>$('dropZone').addEventListener(ev,e=>{e.preventDefault();$('dropZone').classList.remove('dragover')}));
$('dropZone').addEventListener('drop',e=>setFiles(e.dataTransfer.files));
$('imageInput').addEventListener('change',e=>{setFiles(e.target.files);e.target.value=''});
$('quality').addEventListener('input',()=>{$('qualityValue').textContent=$('quality').value+'%';invalidateResults()});
['outputFormat','maxDimension','background'].forEach(id=>$(id).addEventListener('change',()=>{refreshQualityControl();invalidateResults()}));
$('compressImages').addEventListener('click',run);
$('downloadAll').addEventListener('click',()=>{
 outputs.forEach((o,i)=>{const a=document.createElement('a');a.href=o.url;a.download=o.outputName;document.body.appendChild(a);setTimeout(()=>{a.click();a.remove()},i*250)});
});
$('year').textContent=new Date().getFullYear();
setLanguage();
refreshQualityControl();
})();