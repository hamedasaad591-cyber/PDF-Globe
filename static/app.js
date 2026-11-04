/* PDF Globe — client-side PDF tools plus a small API for conversions that need a server. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const API_BASE = String(window.PDF_GLOBE_API_BASE || window.location.origin).replace(/\/+$/, '');
  const apiUrl = (path) => `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const pdfLib = window.PDFLib;
  if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  const I18N = {
    ar: {
      nav_tools:'الأدوات',nav_how:'كيف يعمل',nav_privacy:'الخصوصية',get_started:'ابدأ الآن',eyebrow:'أدوات ملفات متاحة للجميع حول العالم',hero_title:'كل ما تحتاجه لملفاتك<br><em>في مكان واحد.</em>',hero_text:'حوّل ملفات PDF وعدّلها وادمجها واضغطها وترجمها بسهولة. أدوات عملية، بواجهة بسيطة، ومصممة لتعمل معك أينما كنت.',explore_tools:'استكشف الأدوات',free_note:'استخدام مجاني ضمن حدود الخدمة',global_note:'مصمم لمستخدمين من مختلف الدول واللغات',convert:'تحويل الملفات',translate:'ترجمة المستندات',merge:'دمج ملفات PDF',stat_tools:'أداة مفيدة',stat_ui:'لغات للواجهة',stat_signup:'حساب مطلوب للبدء',stat_places:'مستخدمون من كل مكان',tools_kicker:'مساحة العمل',tools_title:'اختر الأداة المناسبة لمهمتك',tools_subtitle:'كل الأدوات الأساسية للملفات والمستندات في واجهة واحدة.',search_tools:'ابحث عن أداة...',cat_all:'كل الأدوات',cat_organize:'تنظيم PDF',cat_convert:'التحويل',cat_edit:'التعديل',cat_security:'الحماية',cat_ocr:'استخراج النص والترجمة',tool_merge:'دمج PDF',desc_merge:'اجمع عدة ملفات في ملف واحد.',tool_split:'تقسيم واستخراج الصفحات',desc_split:'اختر الصفحات التي تريدها.',tool_compress:'ضغط PDF',desc_compress:'قلّل حجم الملف مع محاولة الحفاظ على الجودة.',tool_rotate:'تدوير الصفحات',desc_rotate:'دوّر صفحات المستند بالاتجاه المناسب.',tool_delete:'حذف الصفحات',desc_delete:'احذف الصفحات غير المطلوبة.',tool_reorder:'ترتيب الصفحات',desc_reorder:'أعد ترتيب الصفحات حسب الأرقام.',tool_pdfword:'PDF إلى Word',desc_pdfword:'اختر التحويل الهجين أو الحفاظ على الشكل أو استخراج النص القابل للتحرير.',tool_wordpdf:'Word إلى PDF',desc_wordpdf:'حوّل مستندات Word إلى PDF.',tool_imagepdf:'صور إلى PDF',desc_imagepdf:'حوّل صور JPG وPNG إلى ملف PDF.',tool_pdfimage:'PDF إلى صور',desc_pdfimage:'صدّر صفحات PDF بصيغة JPG داخل ZIP.',tool_watermark:'إضافة علامة مائية',desc_watermark:'أضف نصاً شفافاً على صفحات الملف.',tool_numbers:'ترقيم الصفحات',desc_numbers:'أضف أرقاماً إلى صفحات المستند.',tool_sign:'توقيع PDF',desc_sign:'ارسم توقيعك وأضفه إلى صفحة محددة.',tool_protect:'حماية PDF',desc_protect:'أضف كلمة مرور إلى ملفك.',tool_unlock:'فتح PDF',desc_unlock:'أزل كلمة المرور التي تعرفها.',tool_repair:'إصلاح PDF',desc_repair:'أعد حفظ الملف لمحاولة إصلاح بنيته.',tool_ocr:'استخراج النص OCR',desc_ocr:'استخرج النص من الصور والملفات الممسوحة.',tool_translate:'ترجمة المستندات',desc_translate:'ترجم النص إلى لغة أخرى واحفظه في Word.',no_results:'لم نعثر على أداة بهذا الاسم.',workspace_kicker:'منطقة المعالجة',choose_tool:'اختر أداة للبدء',choose_tool_hint:'اضغط على إحدى الأدوات أعلاه، ثم أضف الملف واتبع التعليمات.',drop_title:'اسحب ملفاتك إلى هنا',drop_subtitle:'أو اختر الملفات من جهازك',browse_files:'اختيار الملفات',accepted_files:'PDF أو صور أو Word حسب الأداة · حتى 50 MB للملف',run_tool:'تنفيذ الأداة',secure_hint:'لا نحتفظ بنسخ دائمة من الملفات على هذا الموقع.',processing:'جارٍ المعالجة...',how_kicker:'سهل من البداية للنهاية',how_title:'ثلاث خطوات، ومهمتك تنتهي',step1_title:'اختر الأداة',step1_text:'حدد ما تريد فعله بملفك من قائمة الأدوات.',step2_title:'أضف الملف',step2_text:'ارفع ملفك واضبط الخيارات المناسبة.',step3_title:'حمّل النتيجة',step3_text:'نزّل الملف بعد انتهاء المعالجة.',privacy_title:'ملفاتك تستحق الخصوصية',privacy_text:'تتم معظم عمليات PDF داخل متصفحك على جهازك. بعض التحويلات والترجمة تحتاج إرسال الملف أو النص إلى الخادم أو مزود الترجمة لتنفيذها. لا ترفع معلومات حساسة إلا إذا كنت موافقاً على طريقة المعالجة.',privacy_point1:'لا نطلب إنشاء حساب',privacy_point2:'حذف الملفات المؤقتة بعد المعالجة',footer_note:'أدوات الملفات للجميع، أينما كانوا.',disclaimer:'هذه المنصة أداة مساعدة. راجع نتائج التحويل والترجمة قبل الاعتماد الرسمي، فقد تختلف الجودة بحسب الملف واللغة.',
      opt_pages:'أرقام الصفحات',opt_pages_hint:'اكتب الأرقام أو النطاقات مثل 1-3,5,8-10. يبدأ الترقيم من 1.',opt_degrees:'زاوية التدوير',opt_all_pages:'كل الصفحات',opt_selected_pages:'صفحات محددة',opt_watermark:'نص العلامة المائية',opt_password:'كلمة المرور',opt_password_hint:'استخدم كلمة مرور قوية واحتفظ بها في مكان آمن.',opt_order:'الترتيب الجديد للصفحات',opt_order_hint:'اكتب أرقام الصفحات بالترتيب المطلوب، مثال: 3,1,2,4.',opt_source:'لغة الملف الأصلية',opt_target:'اللغة المطلوب الترجمة إليها',opt_auto:'تلقائي (مع LibreTranslate فقط)',opt_ocr_lang:'لغات التعرف على النص',opt_ocr_hint:'رموز Tesseract مثل eng+ara+fra. قد يتم تنزيل بيانات اللغة عند أول استخدام.',opt_page:'رقم الصفحة',opt_signature:'ارسم توقيعك داخل المربع',opt_clear:'مسح التوقيع',opt_translation_consent:'أوافق على إرسال النص المستخرج إلى مزود الترجمة الخارجي لمعالجته.',opt_note:'ملاحظة',opt_quality:'جودة الصور',opt_word_mode:'طريقة التحويل إلى Word',opt_word_layout:'مطابقة شكل PDF الأصلي (كل صفحة صورة، والنص غير قابل للتحرير)',opt_word_editable:'استخراج نص قابل للتحرير (تجريبي وقد يخل بترتيب العربية والتنسيق)',opt_word_hybrid:'تحويل ذكي هجين (النص العادي قابل للتحرير، والصفحات المعقدة كصور)',opt_word_mode_hint:'الوضع الهجين هو الخيار الموصى به: الصفحات النصية العادية قابلة للتحرير، أما الصفحات التي يُكتشف أنها جداول أو مخططات أو نماذج أو صور ممسوحة فتحفظ كصور كاملة للمحافظة على ترتيبها. قد تختلف نتيجة الاكتشاف حسب بنية PDF.',word_layout_notice:'تم الحفاظ على شكل الصفحات. محتوى الصفحات مدرج كصور داخل Word ولا يمكن تحرير الكلمات مباشرة.',word_editable_notice:'هذا وضع استخراج نص تجريبي؛ راجع اتجاه العربية وترتيب النص والتنسيق قبل الاعتماد عليه.',word_hybrid_notice:'تم إنشاء ملف Word هجين: النص في الصفحات العادية قابل للتحرير، بينما قد تُدرج الصفحات التي تحتوي على جداول أو مخططات معقدة كصور للحفاظ على شكلها وترتيب عناصرها.',
      error_select:'اختر ملفاً أولاً.',error_pdf:'هذا الملف ليس PDF صالحاً أو تعذر فتحه.',error_pdf_one:'اختر ملف PDF واحداً.',error_two:'اختر ملفين على الأقل.',error_pages:'تحقق من أرقام الصفحات التي أدخلتها.',error_password:'أدخل كلمة المرور.',error_consent:'يجب الموافقة على إرسال النص إلى خدمة الترجمة قبل المتابعة.',error_signature:'ارسم توقيعك أولاً.',error_server:'تعذر تنفيذ العملية على الخادم.',done:'اكتملت العملية بنجاح.',download:'تنزيل الملف',remove:'إزالة',working:'جارٍ تجهيز الملف...',ocr_started:'جارٍ قراءة صفحات الملف...',translation_started:'جارٍ استخراج النص وترجمته...',translation_warning:'الترجمة الآلية قد تخطئ في الأسماء والمصطلحات والتنسيق. راجع النص قبل استخدامه.',pages_count:'عدد الصفحات',file_count:'ملف/ملفات',
    },
    en: {
      nav_tools:'Tools',nav_how:'How it works',nav_privacy:'Privacy',get_started:'Get started',eyebrow:'File tools for everyone, everywhere',hero_title:'Everything your files need<br><em>in one place.</em>',hero_text:'Convert, edit, merge, compress and translate PDF files with practical tools and a simple interface built to work wherever you are.',explore_tools:'Explore tools',free_note:'Free use within service limits',global_note:'Made for people across countries and languages',convert:'File conversion',translate:'Document translation',merge:'Merge PDF files',stat_tools:'Useful tools',stat_ui:'Interface languages',stat_signup:'Account required to start',stat_places:'Users everywhere',tools_kicker:'Workspace',tools_title:'Choose the right tool for your task',tools_subtitle:'Essential PDF and document tools in one workspace.',search_tools:'Search for a tool...',cat_all:'All tools',cat_organize:'Organize PDF',cat_convert:'Convert',cat_edit:'Edit',cat_security:'Security',cat_ocr:'OCR & translation',tool_merge:'Merge PDF',desc_merge:'Combine multiple files into one.',tool_split:'Split / extract pages',desc_split:'Choose the pages you need.',tool_compress:'Compress PDF',desc_compress:'Reduce file size while trying to preserve quality.',tool_rotate:'Rotate pages',desc_rotate:'Rotate document pages to the right direction.',tool_delete:'Delete pages',desc_delete:'Remove pages you do not need.',tool_reorder:'Reorder pages',desc_reorder:'Rearrange pages using page numbers.',tool_pdfword:'PDF to Word',desc_pdfword:'Choose smart hybrid conversion, original page appearance or editable text extraction.',tool_wordpdf:'Word to PDF',desc_wordpdf:'Convert Word documents into PDF.',tool_imagepdf:'Images to PDF',desc_imagepdf:'Turn JPG and PNG images into a PDF.',tool_pdfimage:'PDF to images',desc_pdfimage:'Export PDF pages as JPG images in a ZIP.',tool_watermark:'Add watermark',desc_watermark:'Place translucent text on every page.',tool_numbers:'Add page numbers',desc_numbers:'Insert page numbers into your document.',tool_sign:'Sign PDF',desc_sign:'Draw a signature and add it to a page.',tool_protect:'Protect PDF',desc_protect:'Add a password to your PDF.',tool_unlock:'Unlock PDF',desc_unlock:'Remove a password you already know.',tool_repair:'Repair PDF',desc_repair:'Rewrite the file to attempt structural repair.',tool_ocr:'Extract text (OCR)',desc_ocr:'Recognize text in images and scanned files.',tool_translate:'Translate documents',desc_translate:'Translate extracted text and save it as Word.',no_results:'No tools match your search.',workspace_kicker:'Processing area',choose_tool:'Choose a tool to begin',choose_tool_hint:'Select one of the tools above, add your file and follow the instructions.',drop_title:'Drop your files here',drop_subtitle:'or choose files from your device',browse_files:'Choose files',accepted_files:'PDF, images or Word depending on the tool · up to 50 MB per file',run_tool:'Run tool',secure_hint:'We do not keep permanent copies of your files on this site.',processing:'Processing...',how_kicker:'Easy from start to finish',how_title:'Three steps and you are done',step1_title:'Choose a tool',step1_text:'Select what you want to do from the tools list.',step2_title:'Add your file',step2_text:'Upload your file and adjust the options.',step3_title:'Download result',step3_text:'Download your file when processing is complete.',privacy_title:'Your files deserve privacy',privacy_text:'Most PDF operations run in your browser on your device. Some conversions and translation require sending the file or text to the server or translation provider. Do not upload sensitive information unless you agree with the processing method.',privacy_point1:'No account required',privacy_point2:'Temporary files are deleted after processing',footer_note:'File tools for everyone, wherever they are.',disclaimer:'This platform is an assistant tool. Review converted and translated results before official use; quality can vary by file and language.',
      opt_pages:'Page numbers',opt_pages_hint:'Enter page numbers or ranges, e.g. 1-3,5,8-10. Numbering starts at 1.',opt_degrees:'Rotation angle',opt_all_pages:'All pages',opt_selected_pages:'Selected pages',opt_watermark:'Watermark text',opt_password:'Password',opt_password_hint:'Use a strong password and keep it somewhere safe.',opt_order:'New page order',opt_order_hint:'Enter page numbers in the desired order, e.g. 3,1,2,4.',opt_source:'Document language',opt_target:'Translate into',opt_auto:'Auto (LibreTranslate only)',opt_ocr_lang:'OCR languages',opt_ocr_hint:'Tesseract codes such as eng+ara+fra. Language data may download on first use.',opt_page:'Page number',opt_signature:'Draw your signature in the box',opt_clear:'Clear signature',opt_translation_consent:'I agree to send the extracted text to the external translation provider for processing.',opt_note:'Note',opt_quality:'Image quality',opt_word_mode:'Word conversion mode',opt_word_layout:'Match the original PDF appearance (each page is an image; text is not editable)',opt_word_editable:'Extract editable text (experimental; Arabic order and layout may break)',opt_word_hybrid:'Smart hybrid conversion (plain text editable; complex pages as images)',opt_word_mode_hint:'Recommended: ordinary text pages remain editable. Pages detected as tables, brackets, forms, diagrams or scans are embedded as full-page images to preserve their layout. Detection depends on the PDF structure.',word_layout_notice:'Page appearance was preserved. Page content is embedded as images in Word, so individual words cannot be edited.',word_editable_notice:'This is experimental text extraction. Review Arabic direction, text order and layout before relying on it.',word_hybrid_notice:'A hybrid Word file was created: ordinary text pages are editable; pages detected as complex tables or diagrams may be embedded as images to preserve their layout.',
      error_select:'Choose a file first.',error_pdf:'This is not a valid PDF or it could not be opened.',error_pdf_one:'Choose one PDF file.',error_two:'Choose at least two files.',error_pages:'Check the page numbers you entered.',error_password:'Enter a password.',error_consent:'Consent is required before sending text to the translation service.',error_signature:'Draw your signature first.',error_server:'The server could not complete the operation.',done:'Your file is ready.',download:'Download file',remove:'Remove',working:'Preparing your file...',ocr_started:'Reading document pages...',translation_started:'Extracting and translating text...',translation_warning:'Machine translation can make mistakes in names, terminology and formatting. Review the result before using it.',pages_count:'Pages',file_count:'file(s)',
    },
    fr: {nav_tools:'Outils',nav_how:'Comment ça marche',nav_privacy:'Confidentialité',get_started:'Commencer',eyebrow:'Des outils de fichiers pour tous, partout',hero_title:'Tout pour vos fichiers<br><em>au même endroit.</em>',hero_text:'Convertissez, modifiez, fusionnez, compressez et traduisez vos PDF avec des outils pratiques.',explore_tools:'Voir les outils',free_note:'Utilisation gratuite selon les limites du service',global_note:'Pour tous les pays et toutes les langues',tools_kicker:'Espace de travail',tools_title:'Choisissez l’outil adapté',tools_subtitle:'Les outils essentiels pour PDF et documents.',search_tools:'Rechercher un outil...',cat_all:'Tous les outils',cat_organize:'Organiser PDF',cat_convert:'Convertir',cat_edit:'Modifier',cat_security:'Sécurité',cat_ocr:'OCR et traduction',workspace_kicker:'Zone de traitement',choose_tool:'Choisissez un outil',choose_tool_hint:'Sélectionnez un outil, ajoutez votre fichier et suivez les instructions.',drop_title:'Déposez vos fichiers ici',drop_subtitle:'ou choisissez des fichiers',browse_files:'Choisir des fichiers',run_tool:'Lancer',how_kicker:'Simple du début à la fin',how_title:'Trois étapes simples',step1_title:'Choisir un outil',step2_title:'Ajouter le fichier',step3_title:'Télécharger le résultat',privacy_title:'Vos fichiers méritent la confidentialité',footer_note:'Des outils pour tous, partout.',download:'Télécharger',done:'Opération terminée.',
    },
    es: {nav_tools:'Herramientas',nav_how:'Cómo funciona',nav_privacy:'Privacidad',get_started:'Empezar',eyebrow:'Herramientas de archivos para todos, en cualquier lugar',hero_title:'Todo lo que tus archivos necesitan<br><em>en un solo lugar.</em>',hero_text:'Convierte, edita, combina, comprime y traduce archivos PDF con herramientas prácticas.',explore_tools:'Ver herramientas',free_note:'Uso gratuito dentro de los límites del servicio',global_note:'Diseñado para personas de todos los países e idiomas',tools_kicker:'Espacio de trabajo',tools_title:'Elige la herramienta adecuada',tools_subtitle:'Herramientas esenciales para PDF y documentos.',search_tools:'Buscar herramienta...',cat_all:'Todas',cat_organize:'Organizar PDF',cat_convert:'Convertir',cat_edit:'Editar',cat_security:'Seguridad',cat_ocr:'OCR y traducción',workspace_kicker:'Área de procesamiento',choose_tool:'Elige una herramienta',choose_tool_hint:'Selecciona una herramienta, añade tu archivo y sigue las instrucciones.',drop_title:'Arrastra tus archivos aquí',drop_subtitle:'o selecciona archivos',browse_files:'Elegir archivos',run_tool:'Ejecutar',how_kicker:'Fácil de principio a fin',how_title:'Tres pasos sencillos',step1_title:'Elige una herramienta',step2_title:'Añade tu archivo',step3_title:'Descarga el resultado',privacy_title:'Tus archivos merecen privacidad',footer_note:'Herramientas para todos, en todas partes.',download:'Descargar',done:'Proceso completado.',
    },
    tr: {nav_tools:'Araçlar',nav_how:'Nasıl çalışır',nav_privacy:'Gizlilik',get_started:'Başla',eyebrow:'Herkes için, her yerde dosya araçları',hero_title:'Dosyalarınız için gereken her şey<br><em>tek yerde.</em>',hero_text:'PDF dosyalarını kolayca dönüştürün, düzenleyin, birleştirin, sıkıştırın ve çevirin.',explore_tools:'Araçları keşfet',free_note:'Hizmet sınırları içinde ücretsiz kullanım',global_note:'Farklı ülkeler ve diller için tasarlandı',tools_kicker:'Çalışma alanı',tools_title:'İşiniz için doğru aracı seçin',tools_subtitle:'PDF ve belgeler için temel araçlar.',search_tools:'Araç ara...',cat_all:'Tüm araçlar',cat_organize:'PDF düzenle',cat_convert:'Dönüştür',cat_edit:'Düzenle',cat_security:'Güvenlik',cat_ocr:'OCR ve çeviri',workspace_kicker:'İşlem alanı',choose_tool:'Başlamak için araç seçin',choose_tool_hint:'Bir araç seçin, dosyanızı ekleyin ve talimatları izleyin.',drop_title:'Dosyalarınızı buraya bırakın',drop_subtitle:'veya cihazınızdan seçin',browse_files:'Dosya seç',run_tool:'Çalıştır',how_kicker:'Başından sonuna kolay',how_title:'Üç adımda tamamlayın',step1_title:'Araç seçin',step2_title:'Dosyanızı ekleyin',step3_title:'Sonucu indirin',privacy_title:'Dosyalarınız gizliliği hak ediyor',footer_note:'Herkes için dosya araçları.',download:'Dosyayı indir',done:'İşlem tamamlandı.',
    },
    ur: {nav_tools:'ٹولز',nav_how:'طریقہ کار',nav_privacy:'رازداری',get_started:'شروع کریں',eyebrow:'ہر جگہ ہر شخص کے لیے فائل ٹولز',hero_title:'آپ کی فائلوں کی ہر ضرورت<br><em>ایک جگہ۔</em>',hero_text:'PDF فائلوں کو تبدیل، ترمیم، ضم، کمپریس اور ترجمہ کریں۔',explore_tools:'ٹولز دیکھیں',free_note:'سروس کی حدود میں مفت استعمال',global_note:'تمام ممالک اور زبانوں کے صارفین کے لیے',tools_kicker:'ورک اسپیس',tools_title:'اپنے کام کے لیے ٹول منتخب کریں',tools_subtitle:'PDF اور دستاویزات کے ضروری ٹولز۔',search_tools:'ٹول تلاش کریں...',cat_all:'تمام ٹولز',cat_organize:'PDF ترتیب',cat_convert:'تبدیل کریں',cat_edit:'ترمیم',cat_security:'حفاظت',cat_ocr:'OCR اور ترجمہ',workspace_kicker:'فائل پراسیسنگ',choose_tool:'شروع کرنے کے لیے ٹول منتخب کریں',choose_tool_hint:'اوپر سے ٹول منتخب کریں، فائل شامل کریں اور ہدایات پر عمل کریں۔',drop_title:'فائلیں یہاں چھوڑیں',drop_subtitle:'یا اپنے آلے سے منتخب کریں',browse_files:'فائل منتخب کریں',run_tool:'چلائیں',how_kicker:'شروع سے آخر تک آسان',how_title:'تین آسان مراحل',step1_title:'ٹول منتخب کریں',step2_title:'فائل شامل کریں',step3_title:'نتیجہ ڈاؤن لوڈ کریں',privacy_title:'آپ کی فائلوں کی رازداری اہم ہے',footer_note:'ہر جگہ ہر شخص کے لیے فائل ٹولز۔',download:'فائل ڈاؤن لوڈ کریں',done:'کام مکمل ہوگیا۔'
    }
  };
  const toolMeta = {
    merge:{title:'tool_merge',desc:'desc_merge',accept:'.pdf',multiple:true},split:{title:'tool_split',desc:'desc_split',accept:'.pdf'},compress:{title:'tool_compress',desc:'desc_compress',accept:'.pdf'},rotate:{title:'tool_rotate',desc:'desc_rotate',accept:'.pdf'},delete:{title:'tool_delete',desc:'desc_delete',accept:'.pdf'},reorder:{title:'tool_reorder',desc:'desc_reorder',accept:'.pdf'},'pdf-word':{title:'tool_pdfword',desc:'desc_pdfword',accept:'.pdf'},'word-pdf':{title:'tool_wordpdf',desc:'desc_wordpdf',accept:'.doc,.docx,.odt,.rtf'},'image-pdf':{title:'tool_imagepdf',desc:'desc_imagepdf',accept:'.jpg,.jpeg,.png,.webp',multiple:true},'pdf-image':{title:'tool_pdfimage',desc:'desc_pdfimage',accept:'.pdf'},watermark:{title:'tool_watermark',desc:'desc_watermark',accept:'.pdf'},numbers:{title:'tool_numbers',desc:'desc_numbers',accept:'.pdf'},sign:{title:'tool_sign',desc:'desc_sign',accept:'.pdf'},protect:{title:'tool_protect',desc:'desc_protect',accept:'.pdf'},unlock:{title:'tool_unlock',desc:'desc_unlock',accept:'.pdf'},repair:{title:'tool_repair',desc:'desc_repair',accept:'.pdf'},ocr:{title:'tool_ocr',desc:'desc_ocr',accept:'.pdf,.png,.jpg,.jpeg,.webp'},translate:{title:'tool_translate',desc:'desc_translate',accept:'.pdf'}
  };
  const LANGS = [['ar','العربية / Arabic'],['en','English'],['fr','Français'],['es','Español'],['de','Deutsch'],['it','Italiano'],['pt','Português'],['tr','Türkçe'],['ur','اردو'],['hi','हिन्दी'],['zh','中文'],['ja','日本語'],['ko','한국어'],['ru','Русский'],['nl','Nederlands'],['pl','Polski'],['sv','Svenska'],['fa','فارسی'],['id','Bahasa Indonesia'],['ms','Bahasa Melayu'],['uk','Українська'],['el','Ελληνικά'],['he','עברית'],['vi','Tiếng Việt']];
  let translationLanguages = LANGS;
  let currentLang = 'ar';
  let currentTool = null;
  let selectedFiles = [];
  let category = 'all';
  let signatureDrawn = false;
  const fileInput = $('#fileInput');

  function t(key){return (I18N[currentLang]&&I18N[currentLang][key]) || I18N.en[key] || I18N.ar[key] || key;}
  function applyLanguage(lang){
    currentLang = I18N[lang] ? lang : 'en';
    document.documentElement.lang = currentLang;
    document.documentElement.dir = ['ar','ur'].includes(currentLang) ? 'rtl':'ltr';
    $('#uiLanguage').value = currentLang;
    $$('[data-i18n]').forEach(el=>{const key=el.dataset.i18n;if(t(key)!==key)el.innerHTML=t(key);});
    $$('[data-i18n-placeholder]').forEach(el=>el.placeholder=t(el.dataset.i18nPlaceholder));
    renderToolCards();
    if(currentTool) openTool(currentTool,false);
  }
  $('#uiLanguage').addEventListener('change',e=>applyLanguage(e.target.value));
  $('#year').textContent = new Date().getFullYear();

  function renderToolCards(){
    $$('.tool-card').forEach(card=>{
      const meta=toolMeta[card.dataset.tool];
      card.querySelector('b').textContent=t(meta.title);
      card.querySelector('small').textContent=t(meta.desc);
      const matchesCategory=category==='all'||card.dataset.category===category;
      const query=$('#toolSearch').value.trim().toLocaleLowerCase();
      const hay=(t(meta.title)+' '+t(meta.desc)+' '+card.dataset.tool).toLocaleLowerCase();
      card.classList.toggle('hidden',!matchesCategory||!!query&&!hay.includes(query));
    });
    $('#noResults').classList.toggle('hidden', $$('.tool-card:not(.hidden)').length>0);
  }
  $('#categories').addEventListener('click',e=>{const btn=e.target.closest('button[data-category]');if(!btn)return;category=btn.dataset.category;$$('.category').forEach(x=>x.classList.toggle('active',x===btn));renderToolCards();});
  $('#toolSearch').addEventListener('input',renderToolCards);
  $$('.tool-card').forEach(card=>card.addEventListener('click',()=>openTool(card.dataset.tool)));
  $('#closeWorkspace').addEventListener('click',()=>$('#workspaceSection').classList.remove('visible'));

  function field(label,html,full=false,help=''){return `<div class="option-field ${full?'full':''}"><label>${label}</label>${html}${help?`<small class="option-help">${help}</small>`:''}</div>`;}
  function languageOptions(selected,allowAuto=false){return (allowAuto?`<option value="auto">${t('opt_auto')}</option>`:'')+translationLanguages.map(([code,name])=>`<option value="${code}" ${selected===code?'selected':''}>${name}</option>`).join('');}
  function renderOptions(id){
    const p=$('#optionsPanel');let html='';
    if(['split','delete'].includes(id)) html+=field(t('opt_pages'),`<input id="pageSpec" placeholder="1-3,5,8-10">`,true,t('opt_pages_hint'));
    if(id==='rotate') html+=field(t('opt_degrees'),`<select id="rotation"><option value="90">90°</option><option value="180">180°</option><option value="270">270°</option></select>`)+field(t('opt_pages'),`<input id="pageSpec" placeholder="اتركه فارغاً لتدوير كل الصفحات">`,false,t('opt_pages_hint'));
    if(id==='reorder') html+=field(t('opt_order'),`<input id="pageOrder" placeholder="3,1,2,4">`,true,t('opt_order_hint'));
    if(id==='watermark') html+=field(t('opt_watermark'),`<input id="watermarkText" maxlength="80" placeholder="CONFIDENTIAL / سري">`,true);
    if(['protect','unlock'].includes(id)) html+=field(t('opt_password'),`<input id="password" type="password" autocomplete="new-password" minlength="4">`,true,t('opt_password_hint'));
    if(id==='sign') html+=field(t('opt_page'),`<input id="signPage" type="number" min="1" value="1">`)+field(t('opt_signature'),`<canvas class="signature-pad" id="signaturePad" width="900" height="260"></canvas><button id="clearSignature" type="button" class="browse-btn">${t('opt_clear')}</button>`,true);
    if(id==='ocr') html+=field(t('opt_ocr_lang'),`<input id="ocrLang" value="eng+ara" placeholder="eng+ara+fra">`,true,t('opt_ocr_hint'));
    if(id==='pdf-image') html+=field(t('opt_quality'),`<select id="imageScale"><option value="1">1×</option><option value="1.5" selected>1.5×</option><option value="2">2×</option><option value="3">3×</option></select>`);
    if(id==='pdf-word') html+=field(t('opt_word_mode'),`<select id="wordMode"><option value="hybrid" selected>${t('opt_word_hybrid')}</option><option value="layout">${t('opt_word_layout')}</option><option value="editable">${t('opt_word_editable')}</option></select>`,true,t('opt_word_mode_hint'));
    if(id==='translate'){
      html+=field(t('opt_source'),`<select id="sourceLang">${languageOptions('en',true)}</select>`)+field(t('opt_target'),`<select id="targetLang">${languageOptions('ar')}</select>`);
      html+=field(t('opt_ocr_lang'),`<input id="translateOcrLang" value="eng+ara" placeholder="eng+ara+fra">`,true,t('opt_ocr_hint'));
      html+=`<div class="option-field full"><label class="consent-line"><input type="checkbox" id="translationConsent"><span>${t('opt_translation_consent')}</span></label><small class="option-help">${t('translation_warning')}</small></div>`;
    }
    p.innerHTML=html;p.classList.toggle('hidden',!html);
    if(id==='sign') setupSignature();
    if(id==='translate') $('#targetLang').value=currentLang==='ar'?'en':'ar';
  }
  function openTool(id,scroll=true){
    currentTool=id;selectedFiles=[];fileInput.value='';
    const meta=toolMeta[id];
    $('#workspaceTitle').textContent=t(meta.title);$('#workspaceDescription').textContent=t(meta.desc);
    fileInput.accept=meta.accept;fileInput.multiple=!!meta.multiple;
    $('#fileList').classList.add('hidden');$('#fileList').innerHTML='';
    $('#resultBox').classList.add('hidden');$('#progressWrap').classList.add('hidden');
    $('#runTool').disabled=true;
    $('#acceptedFiles').textContent=`${meta.accept.replaceAll('.', '').toUpperCase()} · ${currentLang==='ar'?'حتى 50 MB للملف':'up to 50 MB per file'}`;
    renderOptions(id);
    $('#workspaceSection').classList.add('visible');
    if(scroll) $('#workspaceSection').scrollIntoView({behavior:'smooth',block:'start'});
  }
  $('#browseFiles').addEventListener('click',()=>fileInput.click());
  $('#uploadArea').addEventListener('click',e=>{if(!e.target.closest('button'))fileInput.click();});
  fileInput.addEventListener('change',()=>setFiles([...fileInput.files]));
  const uploadArea=$('#uploadArea');
  ['dragenter','dragover'].forEach(ev=>uploadArea.addEventListener(ev,e=>{e.preventDefault();uploadArea.classList.add('dragover');}));
  ['dragleave','drop'].forEach(ev=>uploadArea.addEventListener(ev,e=>{e.preventDefault();uploadArea.classList.remove('dragover');}));
  uploadArea.addEventListener('drop',e=>setFiles([...e.dataTransfer.files]));
  function setFiles(files){
    if(!currentTool)return;
    const meta=toolMeta[currentTool];
    selectedFiles=meta.multiple?files:files.slice(0,1);
    if(!selectedFiles.length)return;
    const oversized=selectedFiles.find(f=>f.size>50*1024*1024);
    if(oversized){toast(`${oversized.name}: ${currentLang==='ar'?'الحد الأقصى 50 MB':'maximum 50 MB'}`);selectedFiles=[];return;}
    renderFileList();$('#runTool').disabled=false;$('#resultBox').classList.add('hidden');
  }
  function renderFileList(){
    const list=$('#fileList');list.innerHTML='';list.classList.remove('hidden');
    selectedFiles.forEach((f,i)=>{const row=document.createElement('div');row.className='file-item';row.innerHTML=`<div class="file-meta"><span class="file-badge">${f.name.split('.').pop().slice(0,4).toUpperCase()}</span><div><b></b><small>${formatSize(f.size)}</small></div></div><button class="remove-file" aria-label="remove">×</button>`;row.querySelector('b').textContent=f.name;row.querySelector('button').addEventListener('click',()=>{selectedFiles.splice(i,1);renderFileList();$('#runTool').disabled=!selectedFiles.length;});list.appendChild(row);});
  }
  function formatSize(n){return n<1024*1024?`${(n/1024).toFixed(0)} KB`:`${(n/1024/1024).toFixed(2)} MB`;}
  function toast(message){const node=$('#toast');node.textContent=message;node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),3600);}
  function setProgress(value,label){$('#progressWrap').classList.remove('hidden');$('#progressPercent').textContent=`${Math.round(value)}%`;$('#progressBar').style.width=`${value}%`;if(label)$('#progressText').textContent=label;}
  function finishProgress(){setProgress(100,t('done'));}
  function showResult(blob,filename,notice=''){
    const url=URL.createObjectURL(blob);const box=$('#resultBox');box.innerHTML='';
    const msg=document.createElement('span');msg.textContent=notice||t('done');
    const link=document.createElement('a');link.href=url;link.download=filename;link.className='download-link';link.textContent=t('download');
    box.append(msg,link);box.classList.remove('hidden');
    link.addEventListener('click',()=>setTimeout(()=>URL.revokeObjectURL(url),60000),{once:true});
  }
  function outputName(file,suffix,ext='pdf'){return `${file.name.replace(/\.[^.]+$/,'')}_${suffix}.${ext}`;}
  async function loadPdf(file){try{return await pdfLib.PDFDocument.load(await file.arrayBuffer(),{ignoreEncryption:false});}catch(e){throw new Error(t('error_pdf'));}}
  function parsePageSpec(input,total){
    if(!input||!input.trim())return Array.from({length:total},(_,i)=>i);
    const set=new Set();
    for(const item of input.split(',')){
      const part=item.trim();if(!part)continue;
      const m=part.match(/^(\d+)\s*-\s*(\d+)$/);
      if(m){let a=Number(m[1]),b=Number(m[2]);if(a<1||b<1||a>total||b>total)return null;for(let i=Math.min(a,b);i<=Math.max(a,b);i++)set.add(i-1);}
      else if(/^\d+$/.test(part)){const n=Number(part);if(n<1||n>total)return null;set.add(n-1);}else return null;
    }
    return [...set].sort((a,b)=>a-b);
  }
  async function savePdf(doc,name){const bytes=await doc.save();showResult(new Blob([bytes],{type:'application/pdf'}),name);}
  function addWatermarkCanvas(text){
    const canvas=document.createElement('canvas');canvas.width=1300;canvas.height=230;const c=canvas.getContext('2d');c.clearRect(0,0,canvas.width,canvas.height);c.font='bold 90px "IBM Plex Sans Arabic", Arial, sans-serif';c.fillStyle='rgba(100,110,130,.28)';c.textAlign='center';c.textBaseline='middle';c.fillText(text,650,115,1250);return canvas;
  }
  async function runClientTool(id){
    const files=selectedFiles;
    if(id==='merge'){
      if(files.length<2)throw new Error(t('error_two'));const out=await pdfLib.PDFDocument.create();
      for(const f of files){const src=await loadPdf(f);const pages=await out.copyPages(src,src.getPageIndices());pages.forEach(p=>out.addPage(p));}
      return savePdf(out,`merged_${files.length}_files.pdf`);
    }
    if(['split','delete','rotate','reorder','watermark','numbers','sign'].includes(id)){
      if(files.length!==1)throw new Error(t('error_pdf_one'));const doc=await loadPdf(files[0]);const total=doc.getPageCount();
      if(id==='split'){
        const inds=parsePageSpec($('#pageSpec').value,total);if(!inds||!inds.length)throw new Error(t('error_pages'));
        const out=await pdfLib.PDFDocument.create();const pages=await out.copyPages(doc,inds);pages.forEach(p=>out.addPage(p));return savePdf(out,outputName(files[0],'pages'));
      }
      if(id==='delete'){
        const inds=parsePageSpec($('#pageSpec').value,total);if(!inds||inds.length===total||!inds.length)throw new Error(t('error_pages'));
        [...inds].sort((a,b)=>b-a).forEach(i=>doc.removePage(i));return savePdf(doc,outputName(files[0],'pages_removed'));
      }
      if(id==='rotate'){
        const spec=$('#pageSpec').value.trim();const inds=parsePageSpec(spec,total);if(!inds||!inds.length)throw new Error(t('error_pages'));
        const angle=Number($('#rotation').value);inds.forEach(i=>{const p=doc.getPage(i);p.setRotation(pdfLib.degrees((p.getRotation().angle+angle)%360));});return savePdf(doc,outputName(files[0],'rotated'));
      }
      if(id==='reorder'){
        const order=$('#pageOrder').value.split(',').map(x=>Number(x.trim())-1);if(order.length!==total||order.some(x=>!Number.isInteger(x)||x<0||x>=total)||new Set(order).size!==total)throw new Error(t('error_pages'));
        const out=await pdfLib.PDFDocument.create();const pages=await out.copyPages(doc,order);pages.forEach(p=>out.addPage(p));return savePdf(out,outputName(files[0],'reordered'));
      }
      if(id==='watermark'){
        const text=$('#watermarkText').value.trim();if(!text)throw new Error(t('error_select'));
        const canvas=addWatermarkCanvas(text);const png=await new Promise(r=>canvas.toBlob(r,'image/png'));const image=await doc.embedPng(await png.arrayBuffer());
        doc.getPages().forEach(page=>{const {width,height}=page.getSize();const w=width*.78,h=w*image.height/image.width;page.drawImage(image,{x:(width-w)/2,y:(height-h)/2,width:w,height:h,opacity:.6,rotate:pdfLib.degrees(-28)});});return savePdf(doc,outputName(files[0],'watermarked'));
      }
      if(id==='numbers'){
        const font=await doc.embedFont(pdfLib.StandardFonts.Helvetica);doc.getPages().forEach((page,i)=>{const {width}=page.getSize();page.drawText(String(i+1),{x:width/2-4,y:18,size:10,font,color:pdfLib.rgb(.35,.38,.45)});});return savePdf(doc,outputName(files[0],'numbered'));
      }
      if(id==='sign'){
        const canvas=$('#signaturePad');if(!signatureDrawn)throw new Error(t('error_signature'));const pageNo=Number($('#signPage').value||1);if(pageNo<1||pageNo>total)throw new Error(t('error_pages'));
        const png=await new Promise(r=>canvas.toBlob(r,'image/png'));const image=await doc.embedPng(await png.arrayBuffer());const page=doc.getPage(pageNo-1);const {width}=page.getSize();const w=Math.min(180,width*.35),h=w*image.height/image.width;page.drawImage(image,{x:45,y:45,width:w,height:h});return savePdf(doc,outputName(files[0],'signed'));
      }
    }
    if(id==='image-pdf'){
      if(!files.length)throw new Error(t('error_select'));const doc=await pdfLib.PDFDocument.create();
      for(const f of files){let bytes=await f.arrayBuffer();let type=f.type;
        if(type==='image/webp'){const image=await createImageBitmap(f);const c=document.createElement('canvas');c.width=image.width;c.height=image.height;c.getContext('2d').drawImage(image,0,0);bytes=await new Promise(r=>c.toBlob(r,'image/png')).then(b=>b.arrayBuffer());type='image/png';}
        const img=type==='image/png'?await doc.embedPng(bytes):await doc.embedJpg(bytes);const maxW=595.28,maxH=841.89,scale=Math.min(maxW/img.width,maxH/img.height);const w=img.width*scale,h=img.height*scale;const page=doc.addPage([maxW,maxH]);page.drawImage(img,{x:(maxW-w)/2,y:(maxH-h)/2,width:w,height:h});
      }return savePdf(doc,'images_converted.pdf');
    }
    if(id==='pdf-image'){
      const file=files[0];if(!file)throw new Error(t('error_select'));const scale=Number($('#imageScale').value||1.5);const task=pdfjsLib.getDocument({data:new Uint8Array(await file.arrayBuffer())});const pdf=await task.promise;const zip=new JSZip();
      for(let n=1;n<=pdf.numPages;n++){setProgress((n-1)/pdf.numPages*90,`${t('processing')} ${n}/${pdf.numPages}`);const page=await pdf.getPage(n);const viewport=page.getViewport({scale});const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;const blob=await new Promise(r=>canvas.toBlob(r,'image/jpeg',.9));zip.file(`page-${String(n).padStart(3,'0')}.jpg`,blob);}
      const blob=await zip.generateAsync({type:'blob'});showResult(blob,outputName(file,'images','zip'));return;
    }
    if(id==='ocr'){
      const f=files[0];if(!f)throw new Error(t('error_select'));const lang=$('#ocrLang').value.trim()||'eng';let text='';
      if(f.type==='application/pdf'||f.name.toLowerCase().endsWith('.pdf')){
        const pdf=await pdfjsLib.getDocument({data:new Uint8Array(await f.arrayBuffer())}).promise;
        for(let n=1;n<=pdf.numPages;n++){setProgress((n-1)/pdf.numPages*90,`${t('ocr_started')} ${n}/${pdf.numPages}`);const page=await pdf.getPage(n);const vp=page.getViewport({scale:2});const canvas=document.createElement('canvas');canvas.width=vp.width;canvas.height=vp.height;await page.render({canvasContext:canvas.getContext('2d'),viewport:vp}).promise;const rec=await Tesseract.recognize(canvas,lang,{logger:m=>{if(m.status==='recognizing text')setProgress(((n-1+m.progress)/pdf.numPages)*90,`${t('ocr_started')} ${n}/${pdf.numPages}`);}});text+=`\n\n--- Page ${n} ---\n${rec.data.text}`;}
      }else{const rec=await Tesseract.recognize(f,lang,{logger:m=>{if(m.status==='recognizing text')setProgress(m.progress*90,t('ocr_started'));}});text=rec.data.text;}
      const blob=new Blob([text],{type:'text/plain;charset=utf-8'});showResult(blob,outputName(f,'ocr','txt'));return;
    }
    throw new Error(t('error_server'));
  }
  async function extractPdfText(file, ocrLang='eng+ara'){
    const pdf=await pdfjsLib.getDocument({data:new Uint8Array(await file.arrayBuffer())}).promise;let text='';
    for(let n=1;n<=pdf.numPages;n++){
      setProgress((n-1)/pdf.numPages*35,`${t('translation_started')} ${n}/${pdf.numPages}`);
      const page=await pdf.getPage(n);const content=await page.getTextContent();const items=content.items.map(i=>i.str).filter(Boolean);
      let pageText=items.join(' ');
      // If a page has no selectable text, OCR that page in the visitor's browser.
      if(pageText.trim().length<3){
        const viewport=page.getViewport({scale:2});const canvas=document.createElement('canvas');canvas.width=viewport.width;canvas.height=viewport.height;
        await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;
        const recognized=await Tesseract.recognize(canvas,ocrLang,{logger:m=>{if(m.status==='recognizing text')setProgress(((n-1+m.progress)/pdf.numPages)*35,`${t('translation_started')} ${n}/${pdf.numPages}`);}});
        pageText=recognized.data.text||'';
      }
      text+=`\n\n[Page ${n}]\n`+pageText;
    }
    return text;
  }
  async function apiFile(path,file,extra={}){
    const form=new FormData();form.append('file',file);Object.entries(extra).forEach(([k,v])=>form.append(k,v));
    const response=await fetch(apiUrl(path),{method:'POST',body:form});
    if(!response.ok){let message=t('error_server');try{const data=await response.json();message=data.detail||message;}catch{}throw new Error(message);}
    return response.blob();
  }
  async function runServerTool(id){
    const f=selectedFiles[0];if(!f)throw new Error(t('error_select'));
    if(id==='compress'){const blob=await apiFile('/api/pdf/compress',f);showResult(blob,outputName(f,'compressed'));return;}
    if(id==='pdf-word'){const mode=$('#wordMode')?.value||'hybrid';const blob=await apiFile('/api/pdf/to-word',f,{mode});let notice=t(mode==='layout'?'word_layout_notice':mode==='hybrid'?'word_hybrid_notice':'word_editable_notice');if(mode==='hybrid'&&window.PDF_GLOBE_HYBRID_SUMMARY){const s=window.PDF_GLOBE_HYBRID_SUMMARY;const editable=Number(s.editablePages),images=Number(s.imagePages);if(Number.isFinite(editable)&&Number.isFinite(images)){notice+=currentLang==='ar'?` الصفحات النصية القابلة للتحرير: ${editable}؛ الصفحات المحفوظة كصور: ${images}.`:` Editable text pages: ${editable}; pages preserved as images: ${images}.`;}}showResult(blob,outputName(f,'converted','docx'),notice);return;}
    if(id==='word-pdf'){const blob=await apiFile('/api/word/to-pdf',f);showResult(blob,outputName(f,'converted'));return;}
    if(id==='repair'){const blob=await apiFile('/api/pdf/repair',f);showResult(blob,outputName(f,'repaired'));return;}
    if(id==='protect'||id==='unlock'){
      const password=$('#password').value;if(!password)throw new Error(t('error_password'));
      const blob=await apiFile(`/api/pdf/${id}`,f,{password});showResult(blob,outputName(f,id==='protect'?'protected':'unlocked'));return;
    }
    if(id==='translate'){
      if(!$('#translationConsent').checked)throw new Error(t('error_consent'));
      setProgress(5,t('translation_started'));const extracted=await extractPdfText(f,$('#translateOcrLang').value.trim()||'eng+ara');if(!extracted.trim())throw new Error('No text layer found. Run OCR first for scanned PDFs.');
      const tr=await fetch(apiUrl('/api/translate'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:extracted,source:$('#sourceLang').value,target:$('#targetLang').value})});
      const data=await tr.json();if(!tr.ok)throw new Error(data.detail||t('error_server'));setProgress(80,t('processing'));
      const doc=await fetch(apiUrl('/api/translate/docx'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({translated_text:data.translated_text,target:$('#targetLang').value})});if(!doc.ok){const err=await doc.json();throw new Error(err.detail||t('error_server'));}
      const blob=await doc.blob();showResult(blob,outputName(f,'translated','docx'),`${t('done')} ${t('translation_warning')}`);return;
    }
  }
  $('#runTool').addEventListener('click',async()=>{
    if(!currentTool||!selectedFiles.length)return;
    $('#runTool').disabled=true;$('#resultBox').classList.add('hidden');setProgress(2,t('working'));
    try{
      const client=['merge','split','delete','rotate','reorder','watermark','numbers','sign','image-pdf','pdf-image','ocr'];
      if(client.includes(currentTool))await runClientTool(currentTool);else await runServerTool(currentTool);
      finishProgress();
    }catch(err){toast(err.message||t('error_server'));$('#progressWrap').classList.add('hidden');}
    finally{$('#runTool').disabled=false;}
  });
  function setupSignature(){
    const canvas=$('#signaturePad');if(!canvas)return;const ctx=canvas.getContext('2d');ctx.lineWidth=6;ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#17243c';
    const point=e=>{const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height};};
    let drawing=false;canvas.addEventListener('pointerdown',e=>{drawing=true;canvas.setPointerCapture(e.pointerId);const p=point(e);ctx.beginPath();ctx.moveTo(p.x,p.y);});
    canvas.addEventListener('pointermove',e=>{if(!drawing)return;const p=point(e);ctx.lineTo(p.x,p.y);ctx.stroke();signatureDrawn=true;});
    canvas.addEventListener('pointerup',()=>drawing=false);canvas.addEventListener('pointercancel',()=>drawing=false);
    $('#clearSignature').addEventListener('click',()=>{ctx.clearRect(0,0,canvas.width,canvas.height);signatureDrawn=false;});
  }

  // Configure language direction and initial tool cards.
  applyLanguage('ar');
  // Deep links from SEO landing pages open the requested tool in the main workspace.
  const requestedTool = new URLSearchParams(window.location.search).get('tool');
  if (requestedTool && Object.prototype.hasOwnProperty.call(toolMeta, requestedTool)) {
    openTool(requestedTool, false);
  }
  // Show API readiness in browser console for operators, without exposing secrets.
  fetch(apiUrl('/api/health')).then(r=>r.json()).then(data=>{document.documentElement.dataset.apiReady=data.ok?'true':'false';}).catch(()=>{document.documentElement.dataset.apiReady='false';});
  fetch(apiUrl('/api/languages')).then(r=>r.json()).then(data=>{if(Array.isArray(data.languages)&&data.languages.length){translationLanguages=data.languages.map(x=>[x.code,x.name||x.code]);if(currentTool==='translate')renderOptions('translate');}}).catch(()=>{});
})();
