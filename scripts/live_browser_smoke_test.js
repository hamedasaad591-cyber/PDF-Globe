const { chromium } = require('playwright');

const BASE = 'https://pdf-globe.pages.dev';
const EXPECTED_TOOLS = [
  'merge','split','compress','rotate','delete','reorder','pdf-word','word-pdf',
  'image-pdf','pdf-image','excel-pdf','powerpoint-pdf','watermark','numbers',
  'sign','protect','unlock','repair','ocr','translate','dicom-pdf','dwg-pdf'
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

(async () => {
  let browser;
  const failures = [];
  let simulatedHealthRequests = 0;
  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage']
    });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      ignoreHTTPSErrors: false
    });

    // The monitor checks the deployed API separately. Stub only these read-only
    // discovery calls so this browser test never sends uploaded data or jobs.
    await context.route('https://pdf-globe.onrender.com/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/api/health') {
        simulatedHealthRequests += 1;
        // Simulate Render's free-instance wake-up: two temporary 503 responses,
        // then a healthy JSON response. The page must recover without a reload.
        if (simulatedHealthRequests <= 2) {
          return route.fulfill({
            status: 503,
            contentType: 'text/html',
            body: '<!doctype html><title>Application loading</title>'
          });
        }
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            translation_provider: 'MyMemory',
            capabilities: {}
          })
        });
      }
      if (url.pathname === '/api/languages') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ languages: [] })
        });
      }
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Write requests are disabled in this UI monitor' })
      });
    });

    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    page.on('pageerror', error => failures.push('Browser JavaScript error: ' + error.message));

    const response = await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    assert(response && response.status() === 200,
      'Public Arabic homepage did not return HTTP 200');

    await page.waitForFunction(
      () => !!window.PDFLib && document.querySelectorAll('.tool-card[data-tool]').length > 0,
      null,
      { timeout: 60000 }
    );

    await page.waitForFunction(
      () => document.documentElement.dataset.apiReady === 'true',
      null,
      { timeout: 25000 }
    );
    assert(simulatedHealthRequests >= 3,
      'Frontend did not retry temporary Render 503 responses; health requests: ' + simulatedHealthRequests);
    console.log('PASS API wake-up recovery: recovered after ' + (simulatedHealthRequests - 1) +
      ' temporary 503 responses without reloading the page');

    const ids = await page.locator('.tool-card[data-tool]').evaluateAll(cards =>
      cards.map(card => card.getAttribute('data-tool'))
    );
    assert(ids.length === EXPECTED_TOOLS.length,
      'Expected 22 tool cards; found ' + ids.length);
    assert(new Set(ids).size === ids.length, 'Homepage contains duplicate tool card IDs');

    const missing = EXPECTED_TOOLS.filter(id => !ids.includes(id));
    const unexpected = ids.filter(id => !EXPECTED_TOOLS.includes(id));
    assert(!missing.length && !unexpected.length,
      'Homepage tool registry mismatch. Missing: ' + missing.join(', ') +
      '; unexpected: ' + unexpected.join(', '));

    const totalCards = await page.locator('.tool-card').count();
    assert(totalCards >= 31,
      'Expected at least 31 homepage tools including standalone utilities; found ' + totalCards);
    console.log('PASS live homepage: HTTP 200, PDFLib loaded, 22 interactive cards and ' + totalCards + ' total tool cards');

    for (const id of EXPECTED_TOOLS) {
      const card = page.locator('.tool-card[data-tool="' + id + '"]');
      await card.click();

      const workspace = await page.evaluate(() => {
        const section = document.querySelector('#workspaceSection');
        const title = document.querySelector('#workspaceTitle');
        const input = document.querySelector('#fileInput');
        const runButton = document.querySelector('#runTool');
        return {
          visible: !!section && section.classList.contains('visible'),
          title: title ? title.textContent.trim() : '',
          accept: input ? input.accept.trim() : '',
          multiple: input ? input.multiple : false,
          runButton: !!runButton,
          runDisabled: runButton ? runButton.disabled : true
        };
      });

      assert(workspace.visible, id + ': tool workspace did not open');
      assert(workspace.title.length >= 2, id + ': workspace title is missing');
      assert(workspace.accept.length > 0, id + ': accepted file types are missing');
      assert(workspace.runButton, id + ': run button is missing');
      assert(workspace.runDisabled, id + ': run button should be disabled before file selection');
      console.log('PASS live tool card ' + id + ': workspace, title, upload types and idle state');
    }

    // Mobile layout, navigation, search, and language switching are tested
    // against the public site at real phone viewport widths.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForFunction(
      () => document.querySelectorAll('.tool-card[data-tool]').length === 22,
      null,
      { timeout: 60000 }
    );

    for (const width of [390, 360, 320]) {
      await page.setViewportSize({ width, height: 844 });
      const mobile = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
        menuVisible: (() => {
          const summary = document.querySelector('#mobileMenu > summary');
          return !!summary && getComputedStyle(summary).display !== 'none';
        })(),
        toolCards: document.querySelectorAll('.tool-card[data-tool]').length,
        overflowers: [...document.querySelectorAll('body *')].map(node => {
          const rect = node.getBoundingClientRect();
          const style = getComputedStyle(node);
          return {
            tag: node.tagName.toLowerCase(),
            id: node.id || '',
            className: typeof node.className === 'string' ? node.className.slice(0, 100) : '',
            left: Math.round(rect.left * 10) / 10,
            right: Math.round(rect.right * 10) / 10,
            width: Math.round(rect.width * 10) / 10,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
            position: style.position
          };
        }).filter(item => item.right > window.innerWidth + 0.5 || item.left < -0.5)
          .sort((a, b) => b.right - a.right).slice(0, 12)
      }));
      console.log('MOBILE LAYOUT DIAGNOSTICS ' + width + 'px: ' + JSON.stringify(mobile.overflowers));
      assert(mobile.document <= mobile.viewport + 1,
        'Horizontal page overflow at ' + width + 'px: document is ' + mobile.document + 'px');
      assert(mobile.body <= mobile.viewport + 1,
        'Horizontal body overflow at ' + width + 'px: body is ' + mobile.body + 'px');
      assert(mobile.menuVisible, 'Mobile navigation is not visible at ' + width + 'px');
      assert(mobile.toolCards === EXPECTED_TOOLS.length,
        'Mobile page lost tool cards at ' + width + 'px');
      console.log('PASS mobile layout ' + width + 'px: no horizontal overflow, navigation and all tool cards present');
    }

    const menuSummary = page.locator('#mobileMenu > summary');
    await menuSummary.click();
    assert(await page.locator('#mobileMenu').evaluate(node => node.open),
      'Mobile navigation did not open');
    const menuBounds = await page.locator('#mobileMenu .mobile-menu-panel').evaluate(node => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, viewport: window.innerWidth };
    });
    assert(menuBounds.left >= -0.5 && menuBounds.right <= menuBounds.viewport + 0.5,
      'Mobile navigation panel extends beyond the viewport: ' + JSON.stringify(menuBounds));
    console.log('PASS mobile navigation panel stays within the viewport');
    await page.locator('#mobileMenu .mobile-menu-panel a[href="#tools"]').click();
    assert(!(await page.locator('#mobileMenu').evaluate(node => node.open)),
      'Mobile navigation did not close after choosing a menu item');
    console.log('PASS mobile navigation: opens and closes after link selection');

    await page.locator('#toolSearch').fill('merge');
    const filteredCards = page.locator('.tool-card[data-tool]:not(.hidden)');
    assert(await filteredCards.count() === 1,
      'Mobile tool search should show exactly one result for "merge"');
    assert(await filteredCards.first().getAttribute('data-tool') === 'merge',
      'Mobile tool search returned the wrong tool');
    await page.locator('#toolSearch').fill('');
    console.log('PASS mobile tool search: filters to the matching tool and resets');

    await page.locator('#uiLanguage').selectOption('en');
    await page.waitForURL(url => url.pathname === '/en/' || url.pathname === '/en',
      { timeout: 15000 });
    const languageState = await page.evaluate(() => ({
      lang: document.documentElement.lang,
      direction: document.documentElement.dir,
      cards: document.querySelectorAll('.tool-card[data-tool]').length
    }));
    assert(languageState.lang === 'en', 'Language switch did not load English HTML');
    assert(languageState.direction === 'ltr', 'English page should use left-to-right direction');
    assert(languageState.cards === EXPECTED_TOOLS.length,
      'English homepage does not contain all 22 tool cards');
    console.log('PASS language switching: Arabic homepage navigates to complete English homepage');

    // Load every URL in the production sitemap in Chromium, not just the homepage.
    const sitemapResponse = await page.request.get(BASE + '/sitemap.xml');
    assert(sitemapResponse.ok(), 'Public sitemap is not reachable from the browser');
    const sitemapXml = await sitemapResponse.text();
    const pageUrls = [...sitemapXml.matchAll(/<loc>([^<]+)<\\/loc>/g)].map(match => match[1].trim());
    assert(pageUrls.length >= 30, 'Expected at least 30 public sitemap pages; found ' + pageUrls.length);
    assert(new Set(pageUrls).size === pageUrls.length, 'Public sitemap contains duplicate browser audit URLs');
    for (const url of pageUrls) {
      assert(new URL(url).origin === BASE, 'Sitemap contains a foreign-origin URL: ' + url);
      const pageResponse = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      assert(pageResponse && pageResponse.status() === 200,
        'Sitemap page failed to load in Chromium: ' + url + ' (' + (pageResponse ? pageResponse.status() : 'no response') + ')');
      const state = await page.evaluate(() => ({
        title: document.title.trim(),
        lang: document.documentElement.lang,
        canonical: document.querySelector('link[rel="canonical"]')?.href || '',
        heading: document.querySelector('h1')?.textContent.trim() || ''
      }));
      assert(state.title.length >= 16, 'Page title missing in browser: ' + url);
      assert(['ar', 'en'].includes(state.lang), 'Unsupported page language in browser: ' + url);
      assert(state.canonical === url, 'Canonical URL mismatch in browser: ' + url + ' found ' + state.canonical);
      assert(state.heading.length >= 5, 'Main heading missing in browser: ' + url);
    }
    console.log('PASS Chromium navigation and metadata for all ' + pageUrls.length + ' sitemap pages');

    if (failures.length) {
      throw new Error(failures.join('\n'));
    }
    console.log('SUMMARY: ' + EXPECTED_TOOLS.length +
      ' of ' + EXPECTED_TOOLS.length + ' public tool cards opened their correct workspace');
    console.log('PASS ALL LIVE BROWSER UI CHECKS');
    await context.close();
  } catch (error) {
    console.error(error && error.stack ? error.stack : error);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
})();
