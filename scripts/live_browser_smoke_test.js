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

    console.log('PASS live homepage: HTTP 200, PDFLib loaded, exactly 22 unique tool cards');

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
