(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const TEXT = {
    ar: {
      home:'الرئيسية',pdfTools:'أدوات PDF',printTools:'أدوات الطباعة',eyebrow:'أداة مجانية — تعمل مباشرة في متصفحك',heading:'محول الوحدات والمقادير',intro:'حوّل الأوزان والأطوال والحجوم ودرجات الحرارة وغيرها بسرعة، أو احسب مقادير الطبخ والوصفات بدقة عملية.',tag1:'لا حاجة للتسجيل',tag2:'لا يتم رفع ملفات',tag3:'يدعم العربية والإنجليزية',converterLabel:'محوّل الوحدات',converterHeading:'حوّل أي قياس إلى وحدة أخرى',instant:'نتيجة فورية',category:'نوع القياس',ingredient:'المكوّن (لتحويل الوزن إلى حجم)',amount:'القيمة',from:'من',to:'إلى',result:'النتيجة',copy:'نسخ النتيجة',note:'التحويلات تقريبية عند الحاجة، وتُعرض النتيجة بدقة مناسبة للاستخدام اليومي.',recipeLabel:'حاسبة الوصفات',recipeHeading:'ضاعف المقادير أو قلّلها حسب عدد الحصص',recipeIntro:'أدخل كمية كل مكوّن، وحدد عدد الحصص الأصلية والمطلوبة لتحصل على المقادير الجديدة.',originalServings:'الحصص الأصلية',targetServings:'الحصص المطلوبة',scaleFactor:'معامل التغيير',ingredientName:'المكوّن',quantity:'الكمية',unit:'الوحدة',newQuantity:'الكمية الجديدة',addIngredient:'+ أضف مكوّناً',copyRecipe:'نسخ الوصفة الجديدة',recipeNote:'هذه الحاسبة تغيّر الكميات حسابياً. راعِ أن أوقات الطهي ودرجات الحرارة لا تتضاعف بالضرورة عند زيادة الحصص.',info1Title:'تحويل الأوزان والمقادير',info1Text:'حوّل بين الغرام والكيلوغرام والرطل والأونصة، وبين الغرامات والأكواب والملاعق وفق نوع المكوّن.',info2Title:'وحدات الحياة اليومية',info2Text:'الطول والمساحة والحجم والحرارة والسرعة والوقت والطاقة والضغط وسعة البيانات الرقمية.',info3Title:'مقادير طبخ عملية',info3Text:'اختر الدقيق أو السكر أو الزبدة أو الأرز أو العسل وغيرها لتحويل الحجم إلى وزن تقريبي مناسب للمكوّن.',faqHeading:'أسئلة شائعة حول تحويل الوحدات',faq1q:'كم غراماً في الكيلوغرام؟',faq1a:'الكيلوغرام الواحد يساوي 1000 غرام بالضبط.',faq2q:'هل الكوب يساوي نفس الوزن لكل المكونات؟',faq2a:'لا. الكوب وحدة حجم، بينما الغرام وحدة وزن؛ لذلك يختلف الوزن حسب كثافة المكوّن وطريقة تعبئته. تستخدم الأداة كثافات تقريبية للمكونات الشائعة.',faq3q:'هل تُرفع بياناتي إلى الخادم؟',faq3a:'لا. عمليات التحويل وحساب الوصفات تتم محلياً داخل متصفحك ولا تحتاج إلى رفع ملفات أو إنشاء حساب.',backHome:'← العودة إلى PDF Globe',footer:'أدوات مجانية وعملية للجميع.',privacy:'الخصوصية',copied:'تم نسخ النتيجة.',copyError:'تعذر النسخ تلقائياً؛ حدد النتيجة وانسخها يدوياً.',invalid:'أدخل قيمة رقمية صحيحة أكبر من أو تساوي صفراً.',invalidServings:'يجب أن يكون عدد الحصص أكبر من صفر.',noRows:'أضف مكوناً واحداً على الأقل.',cat_mass:'الوزن والكتلة',cat_length:'الطول والمسافة',cat_volume:'الحجم والسعة',cat_area:'المساحة',cat_temperature:'درجة الحرارة',cat_speed:'السرعة',cat_time:'الوقت',cat_data:'البيانات الرقمية',cat_pressure:'الضغط',cat_energy:'الطاقة',cat_cooking:'مقادير الطبخ',ing_water:'الماء',ing_flour:'دقيق أبيض متعدد الاستخدامات',ing_sugar:'سكر أبيض',ing_brown:'سكر بني معبأ',ing_butter:'زبدة',ing_rice:'أرز أبيض جاف',ing_oats:'شوفان',ing_cocoa:'كاكاو بودرة',ing_honey:'عسل',ing_salt:'ملح ناعم',ing_milk:'حليب',ing_oil:'زيت زيتون',emptyName:'مثال: دقيق',sample:'مكوّن',kg:'كيلوغرام',g:'غرام',mg:'ملليغرام',tonne:'طن متري',oz:'أونصة',lb:'رطل',st:'ستون',mm:'ملليمتر',cm:'سنتيمتر',m:'متر',km:'كيلومتر',inch:'بوصة',ft:'قدم',yd:'ياردة',mi:'ميل',ml:'ملليلتر',l:'لتر',m3:'متر مكعب',tsp:'ملعقة صغيرة',tbsp:'ملعقة كبيرة',cup:'كوب أمريكي (240 مل)',floz:'أونصة سائلة أمريكية',pt:'باينت أمريكي',qt:'كوارت أمريكي',gal:'غالون أمريكي',mm2:'ملليمتر مربع',cm2:'سنتيمتر مربع',m2:'متر مربع',km2:'كيلومتر مربع',in2:'بوصة مربعة',ft2:'قدم مربع',acre:'أكر',ha:'هكتار',c:'درجة مئوية',f:'درجة فهرنهايت',k:'كلفن',ms:'متر/ثانية',kmh:'كيلومتر/ساعة',mph:'ميل/ساعة',knot:'عقدة',sec:'ثانية',min:'دقيقة',hour:'ساعة',day:'يوم',week:'أسبوع',byte:'بايت',kb:'كيلوبايت (1000 بايت)',mb:'ميغابايت (1000 كيلوبايت)',gb:'غيغابايت',tb:'تيرابايت',kib:'كيبيبايت (1024 بايت)',mib:'ميبيبايت',gib:'غيبيبايت',tib:'تيبيبايت',pa:'باسكال',kpa:'كيلوباسكال',bar:'بار',psi:'رطل/بوصة²',j:'جول',kj:'كيلوجول',kcal:'سعرة حرارية غذائية',wh:'واط ساعة',kwh:'كيلوواط ساعة'
    },
    en: {
      home:'Home',pdfTools:'PDF tools',printTools:'Print tools',eyebrow:'Free tool — runs in your browser',heading:'Unit & Measurement Converter',intro:'Convert weight, length, volume, temperature and more. Calculate cooking measurements and scale recipe quantities in seconds.',tag1:'No sign-up required',tag2:'No file uploads',tag3:'Arabic and English',converterLabel:'Unit converter',converterHeading:'Convert any measurement',instant:'Instant result',category:'Measurement type',ingredient:'Ingredient (for weight ↔ volume)',amount:'Amount',from:'From',to:'To',result:'Result',copy:'Copy result',note:'Conversions are rounded for practical everyday use. Results may be approximate where measurement standards vary.',recipeLabel:'Recipe calculator',recipeHeading:'Scale ingredients to any serving size',recipeIntro:'Enter each ingredient quantity and choose the original and desired servings to calculate adjusted amounts.',originalServings:'Original servings',targetServings:'Desired servings',scaleFactor:'Scaling factor',ingredientName:'Ingredient',quantity:'Quantity',unit:'Unit',newQuantity:'New quantity',addIngredient:'+ Add ingredient',copyRecipe:'Copy scaled recipe',recipeNote:'This calculator scales quantities mathematically. Cooking times and temperatures do not necessarily scale with serving size.',info1Title:'Weight and cooking measures',info1Text:'Convert milligrams, grams, kilograms, pounds and ounces, plus ingredient-aware grams-to-cups and spoon measures.',info2Title:'Everyday unit categories',info2Text:'Length, area, volume, temperature, speed, time, energy, pressure and digital storage units.',info3Title:'Ingredient-aware cooking',info3Text:'Choose flour, sugar, butter, rice, honey and other ingredients to estimate volume-to-weight conversions.',faqHeading:'Frequently asked questions',faq1q:'How many grams are in a kilogram?',faq1a:'One kilogram equals exactly 1,000 grams.',faq2q:'Does one cup weigh the same for every ingredient?',faq2a:'No. A cup measures volume while grams measure mass. Weight changes with ingredient density and packing. This tool uses approximate densities for common ingredients.',faq3q:'Are my values sent to a server?',faq3a:'No. Unit conversions and recipe scaling run locally in your browser. No file upload or account is required.',backHome:'← Back to PDF Globe',footer:'Free practical tools for everyone.',privacy:'Privacy',copied:'Result copied.',copyError:'Automatic copy failed. Select the result and copy it manually.',invalid:'Enter a valid number greater than or equal to zero.',invalidServings:'Serving counts must be greater than zero.',noRows:'Add at least one ingredient.',cat_mass:'Weight & mass',cat_length:'Length & distance',cat_volume:'Volume',cat_area:'Area',cat_temperature:'Temperature',cat_speed:'Speed',cat_time:'Time',cat_data:'Digital storage',cat_pressure:'Pressure',cat_energy:'Energy',cat_cooking:'Cooking measures',ing_water:'Water',ing_flour:'All-purpose flour',ing_sugar:'Granulated sugar',ing_brown:'Packed brown sugar',ing_butter:'Butter',ing_rice:'Dry white rice',ing_oats:'Rolled oats',ing_cocoa:'Cocoa powder',ing_honey:'Honey',ing_salt:'Fine table salt',ing_milk:'Milk',ing_oil:'Olive oil',emptyName:'e.g. Flour',sample:'Ingredient',kg:'Kilogram',g:'Gram',mg:'Milligram',tonne:'Metric tonne',oz:'Ounce',lb:'Pound',st:'Stone',mm:'Millimeter',cm:'Centimeter',m:'Meter',km:'Kilometer',inch:'Inch',ft:'Foot',yd:'Yard',mi:'Mile',ml:'Milliliter',l:'Liter',m3:'Cubic meter',tsp:'Teaspoon',tbsp:'Tablespoon',cup:'US cup (240 mL)',floz:'US fluid ounce',pt:'US pint',qt:'US quart',gal:'US gallon',mm2:'Square millimeter',cm2:'Square centimeter',m2:'Square meter',km2:'Square kilometer',in2:'Square inch',ft2:'Square foot',acre:'Acre',ha:'Hectare',c:'Celsius',f:'Fahrenheit',k:'Kelvin',ms:'Meters/second',kmh:'Kilometers/hour',mph:'Miles/hour',knot:'Knot',sec:'Second',min:'Minute',hour:'Hour',day:'Day',week:'Week',byte:'Byte',kb:'Kilobyte (1000 bytes)',mb:'Megabyte (1000 KB)',gb:'Gigabyte',tb:'Terabyte',kib:'Kibibyte (1024 bytes)',mib:'Mebibyte',gib:'Gibibyte',tib:'Tebibyte',pa:'Pascal',kpa:'Kilopascal',bar:'Bar',psi:'Pound per square inch',j:'Joule',kj:'Kilojoule',kcal:'Kilocalorie',wh:'Watt-hour',kwh:'Kilowatt-hour'
    }
  };
  const FACTORS = {
    mass:{mg:.001,g:1,kg:1000,tonne:1000000,oz:28.349523125,lb:453.59237,st:6350.29318},
    length:{mm:.001,cm:.01,m:1,km:1000,inch:.0254,ft:.3048,yd:.9144,mi:1609.344},
    volume:{ml:1,l:1000,m3:1000000,tsp:5,tbsp:15,cup:240,floz:29.5735295625,pt:473.176473,qt:946.352946,gal:3785.411784},
    area:{mm2:.000001,cm2:.0001,m2:1,km2:1000000,in2:.00064516,ft2:.09290304,acre:4046.8564224,ha:10000},
    speed:{ms:1,kmh:1/3.6,mph:.44704,knot:.5144444444},
    time:{sec:1,min:60,hour:3600,day:86400,week:604800},
    data:{byte:1,kb:1000,mb:1000000,gb:1000000000,tb:1000000000000,kib:1024,mib:1048576,gib:1073741824,tib:1099511627776},
    pressure:{pa:1,kpa:1000,bar:100000,psi:6894.757293},
    energy:{j:1,kj:1000,kcal:4184,wh:3600,kwh:3600000}
  };
  const UNITS = {
    mass:['mg','g','kg','tonne','oz','lb','st'],length:['mm','cm','m','km','inch','ft','yd','mi'],volume:['ml','l','m3','tsp','tbsp','cup','floz','pt','qt','gal'],area:['mm2','cm2','m2','km2','in2','ft2','acre','ha'],temperature:['c','f','k'],speed:['ms','kmh','mph','knot'],time:['sec','min','hour','day','week'],data:['byte','kb','mb','gb','tb','kib','mib','gib','tib'],pressure:['pa','kpa','bar','psi'],energy:['j','kj','kcal','wh','kwh'],cooking:['mg','g','kg','oz','lb','ml','l','tsp','tbsp','cup','floz']
  };
  const INGREDIENTS = {water:1,flour:.5,sugar:.833333,brown:.916667,butter:.945833,rice:.770833,oats:.375,cocoa:.354167,honey:1.416667,salt:1.216667,milk:1.029167,oil:.91};
  const CATEGORIES = ['mass','length','volume','area','temperature','speed','time','data','pressure','energy','cooking'];
  let currentLang = document.documentElement.lang === 'en' ? 'en' : 'ar';
  function t(key){return (TEXT[currentLang] && TEXT[currentLang][key]) || TEXT.en[key] || key;}
  function setTextLanguage(){
    document.documentElement.lang=currentLang;
    document.documentElement.dir=currentLang==='ar'?'rtl':'ltr';
    document.querySelectorAll('[data-t]').forEach(node=>{const key=node.getAttribute('data-t');if(t(key))node.textContent=t(key);});
    $('pageLanguage').value=currentLang;
    refreshSelectLabels();
    renderRecipeRows();
    calculate();
  }
  function refreshSelectLabels(){
    const category=$('category').value || 'mass';
    const selectedFrom=$('fromUnit').value;
    const selectedTo=$('toUnit').value;
    $('category').innerHTML=CATEGORIES.map(k=>'<option value="'+k+'">'+t('cat_'+k)+'</option>').join('');
    $('category').value=category;
    populateUnits(selectedFrom,selectedTo);
    const currentIngredient=$('ingredient').value || 'water';
    $('ingredient').innerHTML=Object.keys(INGREDIENTS).map(k=>'<option value="'+k+'">'+t('ing_'+k)+'</option>').join('');
    $('ingredient').value=currentIngredient;
  }
  function populateUnits(from,to){
    const cat=$('category').value || 'mass';
    const list=UNITS[cat] || UNITS.mass;
    $('fromUnit').innerHTML=list.map(k=>'<option value="'+k+'">'+t(k)+'</option>').join('');
    $('toUnit').innerHTML=list.map(k=>'<option value="'+k+'">'+t(k)+'</option>').join('');
    $('fromUnit').value=list.includes(from)?from:list[0];
    $('toUnit').value=list.includes(to)?to:(list[1] || list[0]);
    $('ingredientField').hidden=cat!=='cooking';
  }
  function pretty(value){
    if(!Number.isFinite(value))return '—';
    if(Object.is(value,-0))value=0;
    return new Intl.NumberFormat(currentLang==='ar'?'ar':'en',{maximumSignificantDigits:9}).format(value);
  }
  function toTemperature(value,unit){
    if(unit==='c')return value+273.15;
    if(unit==='f')return (value-32)*5/9+273.15;
    return value;
  }
  function fromTemperature(k,unit){
    if(unit==='c')return k-273.15;
    if(unit==='f')return (k-273.15)*9/5+32;
    return k;
  }
  function convert(value,cat,from,to,ingredient){
    if(cat==='temperature')return fromTemperature(toTemperature(value,from),to);
    if(cat!=='cooking')return value*FACTORS[cat][from]/FACTORS[cat][to];
    const density=INGREDIENTS[ingredient] || 1;
    const massUnits={mg:.001,g:1,kg:1000,oz:28.349523125,lb:453.59237};
    const volumeUnits={ml:1,l:1000,tsp:5,tbsp:15,cup:240,floz:29.5735295625};
    const fromMass=Object.prototype.hasOwnProperty.call(massUnits,from);
    const toMass=Object.prototype.hasOwnProperty.call(massUnits,to);
    if(fromMass&&toMass)return value*massUnits[from]/massUnits[to];
    if(!fromMass&&!toMass)return value*volumeUnits[from]/volumeUnits[to];
    if(fromMass)return (value*massUnits[from]/density)/volumeUnits[to];
    return (value*volumeUnits[from]*density)/massUnits[to];
  }
  function calculate(){
    const amount=Number($('amount').value);
    if($('amount').value===''||!Number.isFinite(amount)){ $('resultValue').textContent='—';$('resultFormula').textContent='';return; }
    const cat=$('category').value,from=$('fromUnit').value,to=$('toUnit').value;
    if((cat==='temperature'&&toTemperature(amount,from)<0)||(cat!=='temperature'&&amount<0)){ $('resultValue').textContent='—';$('resultFormula').textContent=t('invalid');return; }
    const value=convert(amount,cat,from,to,$('ingredient').value);
    $('resultValue').textContent=pretty(value)+' '+t(to);
    $('resultFormula').textContent=pretty(amount)+' '+t(from)+' = '+pretty(value)+' '+t(to);
  }
  function recipeUnitOptions(selected){
    const opts=['g','kg','mg','oz','lb','ml','l','tsp','tbsp','cup'];
    return opts.map(u=>'<option value="'+u+'" '+(u===selected?'selected':'')+'>'+t(u)+'</option>').join('');
  }
  function renderRecipeRows(){
    const rows=[...$('recipeRows').querySelectorAll('.recipe-row')];
    rows.forEach(row=>{
      const select=row.querySelector('select');
      const current=select.value;
      select.innerHTML=recipeUnitOptions(current);
      select.value=current;
      row.querySelector('.ingredient-name').placeholder=t('emptyName');
    });
  }
  function addRecipeRow(name,amount,unit){
    const row=document.createElement('div');
    row.className='recipe-row';
    row.innerHTML='<input class="ingredient-name" type="text" maxlength="80" placeholder="'+t('emptyName')+'"><input class="ingredient-amount" type="number" min="0" step="any" value="1"><select>'+recipeUnitOptions(unit||'g')+'</select><output>—</output><button type="button" class="remove-row" aria-label="Remove ingredient">×</button>';
    row.querySelector('.ingredient-name').value=name||'';
    row.querySelector('.ingredient-amount').value=amount===undefined?1:amount;
    $('recipeRows').appendChild(row);
    updateRecipe();
  }
  function updateRecipe(){
    const original=Number($('originalServings').value),target=Number($('targetServings').value);
    if(!(original>0)||!(target>0)){ $('scaleFactor').textContent='—';$('recipeRows').querySelectorAll('output').forEach(o=>o.textContent='—');return; }
    const factor=target/original;
    $('scaleFactor').textContent='× '+pretty(factor);
    $('recipeRows').querySelectorAll('.recipe-row').forEach(row=>{
      const amount=Number(row.querySelector('.ingredient-amount').value);
      row.querySelector('output').textContent=Number.isFinite(amount)?pretty(amount*factor)+' '+t(row.querySelector('select').value):'—';
    });
  }
  async function copy(text){
    try{await navigator.clipboard.writeText(text);alert(t('copied'));}
    catch(e){alert(t('copyError'));}
  }
  $('pageLanguage').addEventListener('change',e=>{currentLang=e.target.value;setTextLanguage();});
  $('category').addEventListener('change',()=>{populateUnits();calculate();});
  ['amount','fromUnit','toUnit','ingredient'].forEach(id=>$(id).addEventListener('input',calculate));
  $('swapUnits').addEventListener('click',()=>{const a=$('fromUnit').value;$('fromUnit').value=$('toUnit').value;$('toUnit').value=a;calculate();});
  $('copyResult').addEventListener('click',()=>copy($('resultFormula').textContent||$('resultValue').textContent));
  ['originalServings','targetServings'].forEach(id=>$(id).addEventListener('input',updateRecipe));
  $('recipeRows').addEventListener('input',updateRecipe);
  $('recipeRows').addEventListener('change',updateRecipe);
  $('recipeRows').addEventListener('click',e=>{if(e.target.classList.contains('remove-row')){e.target.closest('.recipe-row').remove();updateRecipe();}});
  $('addIngredient').addEventListener('click',()=>addRecipeRow('',1,'g'));
  $('copyRecipe').addEventListener('click',()=>{
    const original=Number($('originalServings').value),target=Number($('targetServings').value);
    if(!(original>0)||!(target>0)){alert(t('invalidServings'));return;}
    const factor=target/original;
    const lines=['PDF Globe — '+target+' servings'];
    $('recipeRows').querySelectorAll('.recipe-row').forEach(row=>{
      const name=row.querySelector('.ingredient-name').value.trim()||t('sample');
      const amount=Number(row.querySelector('.ingredient-amount').value);
      if(Number.isFinite(amount)&&amount>=0)lines.push(name+': '+pretty(amount*factor)+' '+t(row.querySelector('select').value));
    });
    if(lines.length===1){alert(t('noRows'));return;}
    copy(lines.join('\n'));
  });
  $('year').textContent=new Date().getFullYear();
  refreshSelectLabels();
  populateUnits('kg','g');
  $('category').value='mass';
  $('ingredient').value='water';
  addRecipeRow(t('ing_flour'),250,'g');
  addRecipeRow(t('ing_water'),1,'cup');
  addRecipeRow(t('ing_sugar'),2,'tbsp');
  setTextLanguage();
})();