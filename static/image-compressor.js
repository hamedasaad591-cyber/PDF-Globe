(() => {
'use strict';
const $ = id => document.getElementById(id);
const MAX_FILE = 25 * 1024 * 1024;
const MAX_BATCH = 120 * 1024 * 1024;
const MAX_FILES = 20;
const requestedMode = new URLSearchParams(window.location.search).get('mode');
const MODE = ['convert','resize','compress','enhance'].includes(requestedMode) ? requestedMode : 'compress';
const EXTENSIONS = new Set(['jpg','jpeg','jfif','png','webp','avif','heic','heif','bmp','gif','tif','tiff','ico','tga','ppm','pgm','pbm','pcx']);
const EXT = {jpg:'jpg',jpeg:'jpg',png:'png',webp:'webp',avif:'avif',heic:'heic',bmp:'bmp',gif:'gif',tiff:'tiff',ico:'ico',pdf:'pdf'};
const TXT = {
ar:{
home:'الرئيسية',pdfTools:'أدوات PDF',unitTool:'محول الوحدات',imageTools:'أدوات الصور',
eyebrow:'تحويل وتحسين الصور — معالجة آمنة',heading:'تحويل الصور وضغطها وتحسين جودتها',
intro:'حوّل صورك بين الصيغ الشائعة، غيّر المقاسات حتى مع التكبير، اضغط الملفات، واضبط الحدة والتباين والسطوع قبل الطباعة أو المشاركة.',
tag1:'لا حاجة للتسجيل',tag2:'رفع مؤقت للمعالجة ثم حذف الملفات المؤقتة',
tag3:'JPG · PNG · WebP · AVIF · HEIC · BMP · GIF · TIFF · ICO · PDF',
dropTitle:'اسحب الصور إلى هنا',dropText:'أو اختر صوراً من جهازك — يمكنك تحديد عدة صور',choose:'اختيار الصور',
limits:'الصيغ المدعومة: JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF, ICO وغيرها · حتى 25 MB للصورة · 20 صورة',
format:'صيغة الإخراج',width:'العرض بالبكسل (0 = كما هو)',height:'الارتفاع بالبكسل (0 = كما هو)',
keepAspect:'الحفاظ على نسبة الأبعاد',quality:'جودة الإخراج',sharpen:'زيادة الحدة',contrast:'تحسين التباين',
brightness:'السطوع',background:'خلفية الشفافية عند التحويل إلى JPG',convert:'تحويل الصور الآن',
waiting:'اختر الصور وحدد خيارات التحويل لتبدأ.',resultsTitle:'النتيجة الجاهزة',downloadAll:'تنزيل الملف الناتج',
privacyNote:'الخصوصية: تُرفع الصور إلى خادم PDF Globe لإتمام التحويل والتحسين. تُعالج داخل مجلد مؤقت خاص بالطلب ثم تُحذف عند انتهاء المعالجة. لا ترفع ملفات حساسة إلا إذا كنت مخولاً باستخدامها.',
info1Title:'تحويل الصيغ',info1Text:'حوّل بين JPG وPNG وWebP وAVIF وHEIC وBMP وGIF وTIFF وICO، أو أنشئ PDF من صورك.',
info2Title:'تغيير المقاسات والتكبير',info2Text:'حدد العرض والارتفاع بالبكسل مع الحفاظ على النسبة أو إيقافه. يمكن تكبير الصورة، لكن الاستيفاء لا يعيد التفاصيل التي لم تكن موجودة في الأصل.',
info3Title:'تحسين مظهر الصورة',info3Text:'تحكم في جودة الضغط والحدة والتباين والسطوع. هذه تحسينات تقليدية وليست إعادة بناء تفاصيل بالذكاء الاصطناعي.',
faqTitle:'أسئلة شائعة',faq1q:'ما الصيغ التي تدعمها الأداة؟',
faq1a:'تدعم إدخال JPG وJPEG وJFIF وPNG وWebP وAVIF وHEIC وHEIF وBMP وGIF وTIFF وICO وTGA وPPM وPGM وPBM وPCX. ويمكن إخراج JPG وPNG وWebP وAVIF وHEIC وBMP وGIF وTIFF وICO وPDF.',
faq2q:'هل يمكن تكبير الصورة وزيادة جودتها؟',faq2a:'يمكن تغيير أبعاد الصورة إلى حجم أكبر مع إضافة الحدة والتباين والسطوع. التكبير التقليدي لا يستعيد تفاصيل مفقودة؛ لذلك احتفظ بالملف الأصلي.',
faq3q:'هل يتم رفع الصور إلى الخادم؟',faq3a:'نعم، التحويل الشامل للصيغ يتم على خادم المعالجة. تُحفظ الملفات مؤقتاً خلال الطلب ثم تُحذف بعد انتهاء المعالجة. لا ترفع صوراً أو مستندات حساسة إلا بعد التأكد من صلاحية استخدامها.',
backHome:'← العودة إلى PDF Globe',privacy:'الخصوصية',terms:'الشروط',selected:'صور محددة',ready:'جاهزة للمعالجة',
settingsChanged:'تم تغيير الإعدادات. نفّذ التحويل مرة أخرى لتحديث النتيجة.',processing:'جارٍ تحويل الصور وتحسينها...',done:'اكتملت المعالجة.',
failed:'فشل التحويل',unsupported:'توجد صيغة غير مدعومة. تحقق من امتداد الملف.',tooBig:'يتجاوز أحد الملفات حد 25 MB.',
tooMany:'يمكن معالجة 20 صورة كحد أقصى في المرة.',batchBig:'الحد الإجمالي للدفعة 120 MB.',
invalidDimension:'أدخل أبعاداً صحيحة بين 0 و10000 بكسل.',empty:'الخادم أعاد ملفاً فارغاً.',
fileCount:'عدد الملفات',download:'تنزيل النتيجة',fileReady:'أصبح ملفك جاهزاً للتنزيل.',noImages:'لم يتم اختيار صور بعد.'
},
en:{
home:'Home',pdfTools:'PDF tools',unitTool:'Unit converter',imageTools:'Image tools',
eyebrow:'Image conversion & enhancement',heading:'Convert, compress and enhance images',
intro:'Convert common image formats, resize or upscale dimensions, compress files, and adjust sharpness, contrast and brightness for print or sharing.',
tag1:'No sign-up required',tag2:'Temporary server processing with cleanup',
tag3:'JPG · PNG · WebP · AVIF · HEIC · BMP · GIF · TIFF · ICO · PDF',
dropTitle:'Drop images here',dropText:'Or choose images from your device — multiple files supported',choose:'Choose images',
limits:'Supported input: JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF, ICO and more · up to 25 MB/image · 20 images',
format:'Output format',width:'Width in pixels (0 = unchanged)',height:'Height in pixels (0 = unchanged)',
keepAspect:'Keep aspect ratio',quality:'Output quality',sharpen:'Sharpening',contrast:'Contrast',brightness:'Brightness',
background:'Transparent-image background when exporting JPG',convert:'Convert images now',
waiting:'Choose images and conversion settings to begin.',resultsTitle:'Your output is ready',downloadAll:'Download output file',
privacyNote:'Privacy: images are uploaded to the PDF Globe processing server to perform conversion and enhancement. They are handled in a request-specific temporary folder and removed when processing ends. Do not upload sensitive files unless you are authorized to use them.',
info1Title:'Format conversion',info1Text:'Convert JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF and ICO, or create a PDF from your images.',
info2Title:'Resize and upscale',info2Text:'Set pixel width and height while preserving or changing the aspect ratio. Upscaling is supported, but interpolation cannot recover detail missing from the original.',
info3Title:'Image appearance controls',info3Text:'Adjust compression quality, sharpness, contrast and brightness. These are conventional enhancements, not AI detail reconstruction.',
faqTitle:'Frequently asked questions',faq1q:'Which image formats are supported?',
faq1a:'Input supports JPG, JPEG, JFIF, PNG, WebP, AVIF, HEIC, HEIF, BMP, GIF, TIFF, ICO, TGA, PPM, PGM, PBM and PCX. Output supports JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF, ICO and PDF.',
faq2q:'Can I upscale and improve image quality?',faq2a:'You can resize to larger dimensions and adjust sharpness, contrast and brightness. Conventional upscaling does not restore missing details, so keep the original image.',
faq3q:'Are images uploaded to the server?',faq3a:'Yes. Broad format conversion runs on the processing server. Files are stored temporarily during the request and removed when processing ends. Do not upload sensitive images or documents unless you are authorized to use them.',
backHome:'← Back to PDF Globe',privacy:'Privacy',terms:'Terms',selected:'selected images',ready:'ready to process',
settingsChanged:'Settings changed. Run conversion again to refresh the output.',processing:'Converting and enhancing images...',done:'Processing complete.',
failed:'Conversion failed',unsupported:'One or more files have an unsupported extension.',tooBig:'A file exceeds the 25 MB limit.',
tooMany:'You can process up to 20 images per batch.',batchBig:'The total batch limit is 120 MB.',
invalidDimension:'Enter valid dimensions between 0 and 10000 pixels.',empty:'The server returned an empty file.',
fileCount:'Input files',download:'Download result',fileReady:'Your output is ready to download.',noImages:'No images selected yet.'
}
};
const MODE_COPY={
convert:{
ar:{heading:"تحويل الصور بين الصيغ",intro:"حوّل صورك بين JPG وPNG وWebP وAVIF وHEIC وBMP وGIF وTIFF وICO وPDF. يمكنك تحويل عدة صور دفعة واحدة.",action:"تحويل الصور الآن",info1Title:"صيغ كثيرة في أداة واحدة",info1Text:"استورد صيغ الصور الشائعة ثم اختر صيغة الإخراج المناسبة.",info2Title:"تحويل عدة صور معاً",info2Text:"اختر حتى 20 صورة في العملية الواحدة. عند تعدد النتائج تُجمع في ملف ZIP.",info3Title:"اختر الصيغة المناسبة",info3Text:"WebP وAVIF للويب غالباً، وPNG للشفافية، وJPG للصور الفوتوغرافية.",faqTitle:"أسئلة شائعة",faq1q:"ما الصيغ المدعومة؟",faq1a:"يدعم الإدخال JPG وJPEG وJFIF وPNG وWebP وAVIF وHEIC وHEIF وBMP وGIF وTIFF وICO وTGA وPPM وPGM وPBM وPCX. والإخراج JPG وPNG وWebP وAVIF وHEIC وBMP وGIF وTIFF وICO وPDF.",faq2q:"هل يمكن تحويل عدة صور معاً؟",faq2a:"نعم، حتى 20 صورة في الدفعة الواحدة، بحد 25 MB للصورة و120 MB للدفعة.",faq3q:"هل تُرفع الصور؟",faq3a:"نعم، تتم المعالجة مؤقتاً على خادم PDF Globe ثم تُحذف الملفات المؤقتة عند انتهاء الطلب."},
en:{heading:"Convert images between formats",intro:"Convert images between JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF, ICO and PDF. Process several images in one batch.",action:"Convert images now",info1Title:"Common formats in one tool",info1Text:"Import common image formats and select the output format you need.",info2Title:"Batch conversion",info2Text:"Select up to 20 images. Multiple outputs are combined into a ZIP archive.",info3Title:"Choose a suitable format",info3Text:"WebP and AVIF are useful for the web, PNG for transparency and JPG for photographs.",faqTitle:"Frequently asked questions",faq1q:"Which formats are supported?",faq1a:"Input supports JPG, JPEG, JFIF, PNG, WebP, AVIF, HEIC, HEIF, BMP, GIF, TIFF, ICO, TGA, PPM, PGM, PBM and PCX. Output supports JPG, PNG, WebP, AVIF, HEIC, BMP, GIF, TIFF, ICO and PDF.",faq2q:"Can I convert multiple images?",faq2a:"Yes, up to 20 images per batch, with a 25 MB per-image limit and 120 MB total.",faq3q:"Are images uploaded?",faq3a:"Yes. Files are processed temporarily on the server and temporary files are removed when the request ends."}},
resize:{
ar:{heading:"تكبير وتصغير الصور وتغيير أبعادها",intro:"حدد عرض الصورة وارتفاعها بالبكسل، مع الحفاظ على نسبة الأبعاد أو تحديد أبعاد مستقلة. جهّز صورك للطباعة أو النشر.",action:"تغيير أبعاد الصور",info1Title:"تحكم دقيق بالأبعاد",info1Text:"حدد العرض والارتفاع حتى 10000 بكسل، واترك أحدهما صفراً للاحتفاظ بالبعد الأصلي.",info2Title:"حافظ على تناسب الصورة",info2Text:"فعّل الحفاظ على نسبة الأبعاد لمنع تمدد الصورة أو انضغاطها.",info3Title:"التكبير التقليدي",info3Text:"يمكن تكبير أبعاد الصورة بالاستيفاء، لكن ذلك لا يعيد تفاصيل مفقودة ولا يعادل تحسين الدقة بالذكاء الاصطناعي.",faqTitle:"أسئلة شائعة",faq1q:"هل يمكن تكبير الصورة؟",faq1a:"نعم، أدخل أبعاداً أكبر من الأصل. لا يستطيع التكبير التقليدي استعادة تفاصيل لم تكن موجودة.",faq2q:"كيف أحافظ على شكل الصورة؟",faq2a:"اترك خيار الحفاظ على نسبة الأبعاد مفعلاً، ثم أدخل العرض أو الارتفاع المطلوب.",faq3q:"ما الحد الأقصى للأبعاد؟",faq3a:"يمكن تحديد كل بُعد حتى 10000 بكسل، مع مراعاة حدود المعالجة."},
en:{heading:"Resize and upscale images",intro:"Set image width and height in pixels while preserving the aspect ratio or using independent dimensions. Prepare images for printing and publishing.",action:"Resize images now",info1Title:"Precise dimensions",info1Text:"Set width and height up to 10,000 pixels. Leave one dimension at zero to retain the original.",info2Title:"Keep image proportions",info2Text:"Enable Keep aspect ratio to avoid stretching or squashing the image.",info3Title:"Conventional upscaling",info3Text:"Images can be enlarged through resampling, but this does not recover missing detail or provide AI super-resolution.",faqTitle:"Frequently asked questions",faq1q:"Can I enlarge an image?",faq1a:"Yes. Enter dimensions larger than the original. Conventional resizing cannot restore missing detail.",faq2q:"How do I preserve proportions?",faq2a:"Keep the aspect ratio option enabled and enter the desired width or height.",faq3q:"What is the maximum size?",faq3a:"Each dimension can be set up to 10,000 pixels, subject to processing limits."}},
compress:{
ar:{heading:"ضغط الصور وتقليل حجم الملفات",intro:"قلّل حجم الصور لتسهيل رفعها ومشاركتها وتسريع صفحات الويب. اختر صيغة إخراج وجودة مناسبة.",action:"ضغط الصور الآن",info1Title:"تقليل حجم الملفات",info1Text:"استخدم WebP أو AVIF غالباً للحصول على ملفات أصغر للويب، أو JPG للصور الفوتوغرافية.",info2Title:"تحكم في جودة الضغط",info2Text:"اختر جودة من 1 إلى 100. الجودة الأقل قد تنتج ملفاً أصغر مع احتمال فقد بعض التفاصيل.",info3Title:"راجع النتيجة",info3Text:"مقدار التوفير يعتمد على محتوى الصورة والصيغة المختارة؛ احتفظ بالأصل.",faqTitle:"أسئلة شائعة",faq1q:"هل يؤثر الضغط في الجودة؟",faq1a:"قد يؤدي ضغط JPG وWebP وAVIF إلى فقد بعض التفاصيل بحسب الجودة المختارة.",faq2q:"أي صيغة تنتج ملفاً أصغر؟",faq2a:"WebP وAVIF مناسبتان غالباً للويب، لكن النتيجة تعتمد على الصورة نفسها.",faq3q:"هل تُحذف الصور بعد الضغط؟",faq3a:"تعالج الصور داخل مجلد مؤقت خاص بالطلب ثم تحذف الملفات المؤقتة بعد انتهاء المعالجة."},
en:{heading:"Compress images and reduce file size",intro:"Reduce image file sizes for easier uploads, sharing and faster web pages. Choose a suitable output format and quality.",action:"Compress images now",info1Title:"Reduce file size",info1Text:"WebP or AVIF can often produce smaller web images, while JPG is commonly used for photographs.",info2Title:"Control compression quality",info2Text:"Choose a quality level from 1 to 100. Lower quality may create smaller files with visible detail loss.",info3Title:"Review the result",info3Text:"Savings depend on the image content and selected format. Keep the original file.",faqTitle:"Frequently asked questions",faq1q:"Does compression affect quality?",faq1a:"JPG, WebP and AVIF compression can discard detail depending on the quality level.",faq2q:"Which format creates smaller files?",faq2a:"WebP and AVIF are often suitable for the web, but results depend on the image.",faq3q:"Are images deleted after compression?",faq3a:"Images are processed in a request-specific temporary folder. Temporary files are removed when processing ends."}},
enhance:{
ar:{heading:"تحسين جودة الصور ووضوحها",intro:"حسّن مظهر الصور عبر ضبط الحدة والتباين والسطوع، ثم احفظ النتيجة بصيغة مناسبة. هذه تحسينات تقليدية وليست ترميماً بالذكاء الاصطناعي.",action:"تحسين الصور الآن",info1Title:"زيادة الحدة",info1Text:"ارفع الحدة لإبراز الحواف والتفاصيل الظاهرة. المبالغة قد تزيد التشويش أو تُظهر هالات.",info2Title:"التباين والسطوع",info2Text:"اضبط التباين والسطوع تدريجياً حتى لا تفقد مناطق الظلال أو الإضاءة تفاصيلها.",info3Title:"حدود التحسين",info3Text:"لا تنشئ الأداة تفاصيل جديدة ولا تستعيد أجزاء غير موجودة في الأصل.",faqTitle:"أسئلة شائعة",faq1q:"هل الأداة تستخدم الذكاء الاصطناعي؟",faq1a:"لا. توفر ضبط الحدة والتباين والسطوع بالمعالجة التقليدية ولا تعيد بناء التفاصيل.",faq2q:"كيف أحصل على نتيجة طبيعية؟",faq2a:"ابدأ بقيم منخفضة وزدها تدريجياً، لأن التعديلات القوية قد تزيد التشويش.",faq3q:"هل أستطيع اختيار صيغة أخرى؟",faq3a:"نعم، اختر JPG أو PNG أو WebP قبل تنفيذ التحسين."},
en:{heading:"Enhance image quality and clarity",intro:"Improve image appearance by adjusting sharpness, contrast and brightness, then save in a suitable format. These are conventional adjustments, not AI restoration.",action:"Enhance images now",info1Title:"Sharpen visible details",info1Text:"Increase sharpness to emphasize edges. Excessive sharpening can increase noise or create halos.",info2Title:"Adjust contrast and brightness",info2Text:"Tune contrast and brightness gradually to avoid losing shadow or highlight detail.",info3Title:"Understand the limits",info3Text:"This tool does not create new detail or restore missing image information.",faqTitle:"Frequently asked questions",faq1q:"Does this use AI?",faq1a:"No. It provides conventional sharpness, contrast and brightness adjustments, not AI detail reconstruction.",faq2q:"How can I get a natural result?",faq2a:"Start with low values and gradually increase them. Strong adjustments can amplify noise.",faq3q:"Can I choose another output format?",faq3a:"Yes. Choose JPG, PNG or WebP before processing."}}
};
let lang = document.documentElement.lang === 'en' ? 'en' : 'ar';
let files = [];
let resultUrl = null;
let resultName = '';
function t(key){return (MODE_COPY[MODE] && MODE_COPY[MODE][lang] && MODE_COPY[MODE][lang][key]) || TXT[lang][key] || TXT.en[key] || key;}
function setLanguage(){
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  $('pageLanguage').value = lang;
  document.querySelectorAll('[data-t]').forEach(el => { el.textContent = t(el.dataset.t); });
  configureMode();
  refreshRangeLabels();
  document.title=t('heading')+' — PDF Globe';
  if(files.length) renderSelected();
}
function setStatus(message){ $('status').textContent = message; }
function formatSize(bytes){
  if(bytes < 1024) return bytes + ' B';
  if(bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(2) + ' MB';
}
function extension(file){return (file.name.split('.').pop() || '').toLowerCase();}
function revokeResult(){
  if(resultUrl){ URL.revokeObjectURL(resultUrl); resultUrl = null; }
  resultName = '';
  $('results').hidden = true;
  $('resultGrid').innerHTML = '';
}
function invalidateResults(){
  if(!resultUrl) return;
  revokeResult();
  setStatus(t('settingsChanged'));
}
function renderSelected(){
  const box = $('selectedFiles');
  box.innerHTML = '';
  if(!files.length){ box.hidden = true; return; }
  box.hidden = false;
  files.forEach(file => {
    const chip = document.createElement('span');
    chip.className = 'file-chip';
    chip.textContent = file.name + ' · ' + formatSize(file.size);
    box.appendChild(chip);
  });
}
function setFiles(incoming){
  const next = Array.from(incoming || []);
  if(!next.length){ files = []; renderSelected(); $('compressImages').disabled = true; setStatus(t('noImages')); return; }
  if(next.length > MAX_FILES){ setStatus(t('tooMany')); return; }
  if(next.some(file => !EXTENSIONS.has(extension(file)))){ setStatus(t('unsupported')); return; }
  if(next.some(file => file.size > MAX_FILE)){ setStatus(t('tooBig')); return; }
  if(next.reduce((sum,file)=>sum+file.size,0) > MAX_BATCH){ setStatus(t('batchBig')); return; }
  files = next;
  revokeResult();
  renderSelected();
  $('compressImages').disabled = false;
  setStatus(files.length + ' ' + t('selected') + ' · ' + t('ready'));
}
function configureMode(){
  const visible={
    convert:['outputFormat','quality','background'],
    resize:['outputFormat','width','height','keepAspect','quality','background'],
    compress:['outputFormat','quality','background'],
    enhance:['outputFormat','quality','sharpen','contrast','brightness','background']
  }[MODE]||['outputFormat','quality','background'];
  const allowed=new Set(visible);
  document.querySelectorAll('.options-grid .field').forEach(field=>{
    const control=field.querySelector('select[id],input[id]');
    field.hidden=!control||!allowed.has(control.id);
  });
}
function refreshRangeLabels(){
  $('qualityValue').textContent = $('quality').value + '%';
  $('sharpenValue').textContent = $('sharpen').value;
  $('contrastValue').textContent = $('contrast').value;
  $('brightnessValue').textContent = $('brightness').value;
}
function outputExtension(){return EXT[$('outputFormat').value] || 'bin';}
function downloadOutput(){
  if(!resultUrl) return;
  const a = document.createElement('a');
  a.href = resultUrl;
  a.download = resultName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
function renderResult(blob){
  revokeResult();
  resultUrl = URL.createObjectURL(blob);
  const format = $('outputFormat').value;
  const baseNames={convert:'converted-images',resize:'resized-images',compress:'compressed-images',enhance:'enhanced-images'};
  const operationName=baseNames[MODE]||'processed-images';
  if(blob.type==='application/zip')resultName=operationName+'.zip';
  else if(blob.type==='application/pdf'||format==='pdf')resultName=operationName+'.pdf';
  else {const base=files.length===1?files[0].name.replace(/\.[^.]+$/,''):operationName;resultName=base+'_'+MODE+'.'+outputExtension();}

  const card = document.createElement('article');
  card.className = 'result-card';
  if(blob.type && blob.type.startsWith('image/')){
    const preview = document.createElement('img');
    preview.src = resultUrl;
    preview.alt = resultName;
    card.appendChild(preview);
  }else{
    const preview = document.createElement('div');
    preview.className = 'result-file-icon';
    preview.textContent = blob.type === 'application/pdf' ? 'PDF' : 'ZIP';
    card.appendChild(preview);
  }
  const info = document.createElement('div');
  info.className = 'result-info';
  const title = document.createElement('strong');
  title.textContent = resultName;
  const details = document.createElement('small');
  details.textContent = t('fileCount') + ': ' + files.length + ' · ' + formatSize(blob.size);
  const link = document.createElement('a');
  link.href = resultUrl;
  link.download = resultName;
  link.textContent = t('download');
  info.append(title, details, link);
  card.appendChild(info);
  $('resultGrid').appendChild(card);
  $('results').hidden = false;
  $('downloadAll').onclick = downloadOutput;
  $('downloadAll').textContent = t('downloadAll');
  setStatus(t('fileReady'));
}
async function run(){
  if(!files.length) return;
  const width = Number($('width').value || 0);
  const height = Number($('height').value || 0);
  if(!Number.isInteger(width) || !Number.isInteger(height) || width < 0 || height < 0 || width > 10000 || height > 10000){
    setStatus(t('invalidDimension')); return;
  }
  const button = $('compressImages');
  button.disabled = true;
  revokeResult();
  setStatus(t('processing'));
  const form = new FormData();
  files.forEach(file => form.append('files', file));
  form.append('output_format', $('outputFormat').value);
  form.append('width', String(width));
  form.append('height', String(height));
  form.append('keep_aspect', $('keepAspect').checked ? 'true' : 'false');
  form.append('quality', $('quality').value);
  form.append('sharpen', $('sharpen').value);
  form.append('contrast', $('contrast').value);
  form.append('brightness', $('brightness').value);
  form.append('background', $('background').value);
  try{
    const base = (window.PDF_GLOBE_API_BASE || 'https://pdf-globe.onrender.com').replace(/\/+$/,'');
    const response = await fetch(base + '/api/image/convert', {method:'POST', body:form});
    if(!response.ok){
      let detail = t('failed');
      try{ const data = await response.json(); detail = data.detail || detail; }catch{}
      throw new Error(detail);
    }
    const blob = await response.blob();
    if(!blob.size) throw new Error(t('empty'));
    renderResult(blob);
  }catch(error){
    setStatus(error.message || t('failed'));
  }finally{
    button.disabled = !files.length;
  }
}
$('pageLanguage').addEventListener('change', event => {
  const root=event.target.value==='en'?'/en/':'/';
  window.location.assign(root+'image-compressor.html?mode='+MODE);
});
$('chooseImages').addEventListener('click', event => { event.stopPropagation(); $('imageInput').click(); });
$('dropZone').addEventListener('click', event => { if(!event.target.closest('button')) $('imageInput').click(); });
$('dropZone').addEventListener('keydown', event => {
  if(event.key === 'Enter' || event.key === ' '){ event.preventDefault(); $('imageInput').click(); }
});
['dragenter','dragover'].forEach(name => $('dropZone').addEventListener(name, event => {
  event.preventDefault(); $('dropZone').classList.add('dragover');
}));
['dragleave','drop'].forEach(name => $('dropZone').addEventListener(name, event => {
  event.preventDefault(); $('dropZone').classList.remove('dragover');
}));
$('dropZone').addEventListener('drop', event => setFiles(event.dataTransfer.files));
$('imageInput').addEventListener('change', event => { setFiles(event.target.files); event.target.value = ''; });
$('compressImages').addEventListener('click', run);
$('year').textContent = new Date().getFullYear();
['quality','sharpen','contrast','brightness'].forEach(id => $(id).addEventListener('input', () => {
  refreshRangeLabels(); invalidateResults();
}));
['outputFormat','width','height','keepAspect','background'].forEach(id => $(id).addEventListener('change', invalidateResults));
setLanguage();
})();
