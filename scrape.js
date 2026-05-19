const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const BASE_URL = 'https://poovanna-portfolio.framer.ai';
const OUT_DIR = 'C:\\Users\\vigne\\OneDrive\\Desktop\\Poovanna Portfolio';

const downloaded = new Set();

function download(url, dest) {
  return new Promise((resolve) => {
    const proto = url.startsWith('https') ? https : http;
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const file = fs.createWriteStream(dest);
    proto.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, res => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        download(res.headers.location, dest).then(resolve);
        return;
      }
      res.pipe(file);
      file.on('finish', () => { file.close(); resolve(); });
    }).on('error', resolve);
  });
}

async function scrapePage(browser, url) {
  const page = await browser.newPage();
  const assets = new Set();

  page.on('response', async response => {
    const u = response.url();
    if (downloaded.has(u)) return;
    downloaded.add(u);
    assets.add(u);
  });

  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(5000);

  const html = await page.content();
  const pathname = new URL(url).pathname;
  const htmlPath = path.join(OUT_DIR, pathname === '/' ? 'index.html' : pathname + '.html');
  fs.mkdirSync(path.dirname(htmlPath), { recursive: true });
  fs.writeFileSync(htmlPath, html);
  console.log('Saved page:', url);

  for (const assetUrl of assets) {
    try {
      const u = new URL(assetUrl);
      const ext = path.extname(u.pathname) || '.html';
      const safePath = u.pathname.endsWith('/') ? u.pathname + 'index.html' : u.pathname;
      const filePath = path.join(OUT_DIR, u.hostname, safePath.includes('.') ? safePath : safePath + ext);
      await download(assetUrl, filePath);
      console.log('Downloaded:', assetUrl);
    } catch(e) {}
  }

  await page.close();
}

(async () => {
  const browser = await chromium.launch();
  const pages = ['/', '/work', '/about'];

  for (const p of pages) {
    await scrapePage(browser, BASE_URL + p);
  }

  await browser.close();
  console.log('DONE! Files saved to:', OUT_DIR);
})();