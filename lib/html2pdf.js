/**
 * html2pdf — Render an HTML file to PDF via Playwright headless Chromium.
 *
 * Starts a local HTTP server to serve the HTML and its assets (images, SVGs,
 * CSS), navigates headless Chromium to the page, waits for Mermaid diagrams
 * to render, and prints to PDF.
 *
 * Usage:
 *   node html2pdf.js <directory> <filename.html> <output.pdf>
 */

const { chromium } = require("playwright");
const http = require("http");
const fs = require("fs");
const path = require("path");

const MIME_TYPES = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
};

/**
 * Create a static file server rooted at `dir`.
 */
function createFileServer(dir) {
  return http.createServer((req, res) => {
    const filePath = path.join(
      dir,
      decodeURIComponent(req.url.replace(/^\//, ""))
    );
    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end();
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": MIME_TYPES[ext] || "application/octet-stream",
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

/**
 * Convert an HTML file to PDF.
 *
 * @param {string} dir       - Directory containing the HTML and assets
 * @param {string} htmlName  - Filename of the HTML file (not full path)
 * @param {string} pdfPath   - Full path for the output PDF
 * @param {object} [options] - Optional settings
 * @param {string} [options.format]  - Page format (default: "Letter")
 * @param {object} [options.margin]  - Page margins
 * @returns {Promise<number>} Size of the generated PDF in bytes
 */
async function convert(dir, htmlName, pdfPath, options = {}) {
  const format = options.format || "Letter";
  const margin = options.margin || {
    top: "0.6in",
    bottom: "0.6in",
    left: "0.75in",
    right: "0.75in",
  };

  const server = createFileServer(dir);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;

  let browser;
  try {
    browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto(
      `http://127.0.0.1:${port}/${encodeURIComponent(htmlName)}`,
      { waitUntil: "networkidle" }
    );

    // Wait for Mermaid diagrams to render (if any)
    await page
      .waitForFunction(
        () => {
          const els = document.querySelectorAll(".mermaid");
          return (
            els.length === 0 || [...els].every((el) => el.querySelector("svg"))
          );
        },
        { timeout: 15000 }
      )
      .catch(() => {});

    await page.pdf({
      path: pdfPath,
      format,
      printBackground: true,
      margin,
    });

    return fs.statSync(pdfPath).size;
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

// CLI entry point
if (require.main === module) {
  const [dir, htmlName, pdfPath] = process.argv.slice(2);
  if (!dir || !htmlName || !pdfPath) {
    console.error(
      "Usage: node html2pdf.js <directory> <filename.html> <output.pdf>"
    );
    process.exit(1);
  }
  convert(dir, htmlName, pdfPath).then((size) => {
    console.log(`PDF: ${size} bytes`);
  });
}

module.exports = { convert, createFileServer };
