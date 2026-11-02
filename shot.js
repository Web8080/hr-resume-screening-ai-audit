const { chromium } = require('playwright');
(async () => {
  const [,, input, output] = process.argv;
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + require('path').resolve(input)); await p.screenshot({ path: output, fullPage: true }); await b.close();
})();
