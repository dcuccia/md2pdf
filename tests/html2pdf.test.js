/**
 * Tests for lib/html2pdf — HTML to PDF conversion.
 *
 * These tests verify the file server and conversion logic without
 * launching a full browser (unit tests), plus integration tests
 * that exercise the full Playwright pipeline.
 */

const path = require("path");
const fs = require("fs");
const http = require("http");
const { createFileServer, convert } = require("../lib/html2pdf");

const FIXTURES_DIR = path.join(__dirname, "fixtures");

// Create a minimal HTML fixture for testing
function createTestHtml(dir, filename, content) {
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body { font-family: sans-serif; }</style></head>
<body>${content || "<h1>Test</h1><p>Hello, world!</p>"}</body></html>`;
  const filePath = path.join(dir, filename);
  fs.writeFileSync(filePath, html, "utf-8");
  return filePath;
}

describe("createFileServer", () => {
  let server;

  afterEach(() => {
    if (server) {
      server.close();
      server = null;
    }
  });

  test("serves HTML files with correct content type", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    createTestHtml(tmpDir, "test.html");
    server = createFileServer(tmpDir);
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const port = server.address().port;

    const res = await fetch(`http://127.0.0.1:${port}/test.html`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("text/html");
    const body = await res.text();
    expect(body).toContain("<h1>Test</h1>");

    fs.rmSync(tmpDir, { recursive: true });
  });

  test("returns 404 for missing files", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    server = createFileServer(tmpDir);
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const port = server.address().port;

    const res = await fetch(`http://127.0.0.1:${port}/nonexistent.html`);
    expect(res.status).toBe(404);

    fs.rmSync(tmpDir, { recursive: true });
  });

  test("serves SVG files with correct content type", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    fs.writeFileSync(
      path.join(tmpDir, "chart.svg"),
      '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    );
    server = createFileServer(tmpDir);
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const port = server.address().port;

    const res = await fetch(`http://127.0.0.1:${port}/chart.svg`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/svg+xml");

    fs.rmSync(tmpDir, { recursive: true });
  });

  test("decodes URL-encoded filenames", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    createTestHtml(tmpDir, "my file.html", "<p>Spaces work</p>");
    server = createFileServer(tmpDir);
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const port = server.address().port;

    const res = await fetch(`http://127.0.0.1:${port}/my%20file.html`);
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain("Spaces work");

    fs.rmSync(tmpDir, { recursive: true });
  });
});

describe("convert (integration)", () => {
  // These tests launch headless Chromium — mark as slow
  jest.setTimeout(30000);

  test("generates a PDF from HTML", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    createTestHtml(tmpDir, "test.html");
    const pdfPath = path.join(tmpDir, "output.pdf");

    const size = await convert(tmpDir, "test.html", pdfPath);
    expect(size).toBeGreaterThan(0);
    expect(fs.existsSync(pdfPath)).toBe(true);

    // Verify it's a valid PDF (starts with %PDF)
    const header = fs.readFileSync(pdfPath, "ascii").slice(0, 5);
    expect(header).toBe("%PDF-");

    fs.rmSync(tmpDir, { recursive: true });
  });

  test("respects custom page format and margins", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    createTestHtml(tmpDir, "test.html");
    const pdfPath = path.join(tmpDir, "output.pdf");

    const size = await convert(tmpDir, "test.html", pdfPath, {
      format: "A4",
      margin: { top: "1in", bottom: "1in", left: "1in", right: "1in" },
    });
    expect(size).toBeGreaterThan(0);

    fs.rmSync(tmpDir, { recursive: true });
  });

  test("handles HTML with embedded SVG images", async () => {
    const tmpDir = fs.mkdtempSync(path.join(require("os").tmpdir(), "md2pdf-"));
    fs.writeFileSync(
      path.join(tmpDir, "chart.svg"),
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">' +
        '<rect width="100" height="100" fill="blue"/></svg>'
    );
    createTestHtml(tmpDir, "test.html", '<h1>Charts</h1><img src="chart.svg">');
    const pdfPath = path.join(tmpDir, "output.pdf");

    const size = await convert(tmpDir, "test.html", pdfPath);
    expect(size).toBeGreaterThan(0);

    fs.rmSync(tmpDir, { recursive: true });
  });
});
