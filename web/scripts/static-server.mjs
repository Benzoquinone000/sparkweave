import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";

const distDir = resolve(process.env.WEB_DIST_DIR || join(process.cwd(), "dist"));
const port = Number(process.env.FRONTEND_PORT || 3782);
const host = process.env.HOSTNAME || "0.0.0.0";

const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

function resolveAsset(urlPath) {
  const cleanPath = normalize(decodeURIComponent(urlPath.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
  const assetPath = resolve(distDir, `.${cleanPath}`);
  if (!assetPath.startsWith(distDir)) return join(distDir, "index.html");
  if (existsSync(assetPath) && statSync(assetPath).isFile()) return assetPath;
  return join(distDir, "index.html");
}

createServer((request, response) => {
  const assetPath = resolveAsset(request.url || "/");
  const stream = createReadStream(assetPath);
  response.setHeader("Content-Type", types[extname(assetPath)] || "application/octet-stream");
  stream.on("error", () => {
    response.writeHead(500);
    response.end("SparkWeave static server error");
  });
  stream.pipe(response);
}).listen(port, host, () => {
  console.log(`[SparkWeave Web] Static server http://${host}:${port}`);
  console.log(`[SparkWeave Web] Serving ${distDir}`);
});
